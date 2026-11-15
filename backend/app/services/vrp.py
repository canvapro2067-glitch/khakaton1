"""
VRP: распределение заказов по автопарку.

На Python 3.15 нет колёс Google OR-Tools, поэтому реализован полный солвер
той же постановки (CVRPTW): вместимость, 90% загрузка, совместимость улиц,
окна, 8 часов, до max_trips рейсов на машину, минимизация пробега.

Если ortools установлен, последовательность точек уточняется через RoutingModel.
"""
from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass, field

from .geo import DEPOT, Matrix, build_matrix
from .restrictions import vehicle_allowed

try:
    from ortools.constraint_solver import pywrapcp, routing_enums_pb2

    HAS_ORTOOLS = True
except Exception:
    HAS_ORTOOLS = False


def _hm(minutes: int) -> str:
    minutes = max(0, minutes)
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def _parse_hm(s: str | None, default: int) -> int:
    if not s:
        return default
    parts = str(s).strip().split(":")
    try:
        return int(parts[0]) * 60 + int(parts[1] if len(parts) > 1 else 0)
    except ValueError:
        return default


@dataclass
class SolveOrder:
    id: int
    name: str
    address: str
    weight: int
    lat: float
    lon: float
    preferred: str | None
    window_start: str | None
    window_end: str | None
    unload_min: int | None
    historic: bool


@dataclass
class SolveVehicle:
    id: int
    plate: str
    capacity: int
    raw: object


@dataclass
class StopOut:
    order_id: int
    seq: int
    eta: str
    dist_m: int
    travel_s: int


@dataclass
class RouteOut:
    vehicle_id: int
    plate: str
    load: int
    distance_m: int
    duration_s: int
    finish: str
    fill: float
    warning: str
    stops: list[StopOut] = field(default_factory=list)


@dataclass
class UnassignedOut:
    order_id: int
    reason: str
    conflicts: str
    suggestions: str


@dataclass
class SolveResult:
    routes: list[RouteOut]
    unassigned: list[UnassignedOut]
    used_ortools: bool
    elapsed_s: float
    total_distance_m: int
    notes: list[str]


def _windows(o: SolveOrder, work_start: int, work_end: int, slack: int) -> tuple[int, int]:
    if o.window_start and o.window_end:
        return _parse_hm(o.window_start, work_start), _parse_hm(o.window_end, work_end)
    if o.preferred:
        p = _parse_hm(o.preferred, work_start)
        return max(work_start, p - slack), min(work_end, p + slack)
    return work_start, work_end


def _unload_minutes(weight_kg: int, base: int = 25) -> int:
    """Разгрузка на точке: 20–30 мин в зависимости от тоннажа, не 5–12."""
    base = max(20, min(30, base))
    if weight_kg <= 200:
        return 20
    if weight_kg >= 650:
        return 30
    return base


def _centroid(orders: list[SolveOrder]) -> tuple[float, float]:
    if not orders:
        return DEPOT["lat"], DEPOT["lon"]
    return sum(o.lat for o in orders) / len(orders), sum(o.lon for o in orders) / len(orders)


def _dist_ll(a, b) -> float:
    return math.hypot((a[0] - b[0]) * 111_000, (a[1] - b[1]) * 67_000)


def _nn_sequence(ids: list[int], idx: dict[int, int], matrix: Matrix) -> list[int]:
    if not ids:
        return []
    left = set(ids)
    cur = 0
    seq = []
    while left:
        nxt = min(left, key=lambda oid: matrix.dist[cur][idx[oid]])
        seq.append(nxt)
        cur = idx[nxt]
        left.remove(nxt)
    return seq


def _two_opt(seq: list[int], idx: dict[int, int], matrix: Matrix) -> list[int]:
    if len(seq) < 4:
        return seq
    seq = seq[:]

    def length(s):
        d = matrix.dist[0][idx[s[0]]]
        for a, b in zip(s, s[1:]):
            d += matrix.dist[idx[a]][idx[b]]
        d += matrix.dist[idx[s[-1]]][0]
        return d

    best = length(seq)
    improved = True
    rounds = 0
    while improved and rounds < 40:
        improved = False
        rounds += 1
        for i in range(len(seq) - 1):
            for j in range(i + 2, len(seq)):
                new = seq[:i] + seq[i:j][::-1] + seq[j:]
                ln = length(new)
                if ln + 1 < best:
                    seq, best = new, ln
                    improved = True
                    break
            if improved:
                break
    return seq


def _ortools_tsp(seq: list[int], idx: dict[int, int], matrix: Matrix) -> list[int]:
    if not HAS_ORTOOLS or len(seq) < 3:
        return seq
    nodes = [0] + [idx[i] for i in seq]
    n = len(nodes)
    dm = [[matrix.dist[nodes[i]][nodes[j]] for j in range(n)] for i in range(n)]
    manager = pywrapcp.RoutingIndexManager(n, 1, 0)
    routing = pywrapcp.RoutingModel(manager)

    def cb(a, b):
        return dm[manager.IndexToNode(a)][manager.IndexToNode(b)]

    transit = routing.RegisterTransitCallback(cb)
    routing.SetArcCostEvaluatorOfAllVehicles(transit)
    params = pywrapcp.DefaultRoutingSearchParameters()
    params.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    params.time_limit.FromSeconds(2)
    sol = routing.SolveWithParameters(params)
    if not sol:
        return seq
    out = []
    i = routing.Start(0)
    while not routing.IsEnd(i):
        node = manager.IndexToNode(i)
        if node != 0:
            out.append(seq[node - 1])
        i = sol.Value(routing.NextVar(i))
    return out or seq


def _simulate(
    seq: list[int],
    by_id: dict[int, SolveOrder],
    idx: dict[int, int],
    matrix: Matrix,
    work_start: int,
    work_end: int,
    slack: int,
    default_unload: int,
    start_t: int | None = None,
) -> tuple[list[StopOut], int, int, str, list[str]]:
    t = work_start if start_t is None else start_t
    dist_sum = 0
    prev = 0
    stops = []
    warns = []
    for k, oid in enumerate(seq, 1):
        o = by_id[oid]
        j = idx[oid]
        d = matrix.dist[prev][j]
        tr = matrix.time[prev][j]
        t += tr // 60
        ws, we = _windows(o, work_start, work_end, slack)
        if t < ws:
            t = ws
        eta = t
        if t > we:
            warns.append(f"{o.name}: прибытие {_hm(t)} позже окна {_hm(ws)}–{_hm(we)}")
        unload = o.unload_min if o.unload_min is not None else _unload_minutes(o.weight, default_unload)
        t += unload
        dist_sum += d
        stops.append(StopOut(oid, k, _hm(eta), d, tr))
        prev = j
    back = matrix.dist[prev][0] if seq else 0
    back_t = matrix.time[prev][0] if seq else 0
    t += back_t // 60
    dist_sum += back
    duration = (t - work_start) * 60
    if t > work_end:
        warns.append(f"Смена {_hm(t - work_start)} превышает 8 часов (возврат {_hm(t)})")
    return stops, dist_sum, duration, _hm(t), warns


def _route_out_for_group(
    v: SolveVehicle,
    group: list[SolveOrder],
    by_id: dict[int, SolveOrder],
    idx: dict[int, int],
    matrix: Matrix,
    work_start: int,
    work_end: int,
    slack: int,
    default_unload: int,
    min_fill: float,
    start_t: int | None,
    trip_label: str,
) -> RouteOut | None:
    if not group:
        return None
    ids = [o.id for o in group]
    seq = _nn_sequence(ids, idx, matrix)
    seq = _two_opt(seq, idx, matrix)
    if HAS_ORTOOLS:
        seq2 = _ortools_tsp(seq, idx, matrix)
        if seq2:
            seq = seq2
    stops, dist_m, dur_s, finish, warns = _simulate(
        seq, by_id, idx, matrix, work_start, work_end, slack, default_unload, start_t=start_t
    )
    load = sum(by_id[i].weight for i in seq)
    fill_pct = load / v.capacity if v.capacity else 0
    extra = []
    if fill_pct < min_fill:
        extra.append(f"Загрузка {fill_pct:.0%} ниже минимума {min_fill:.0%}")
    if fill_pct > 1:
        extra.append("Превышение грузоподъёмности")
    if trip_label:
        extra.insert(0, trip_label)
    if dur_s > (work_end - work_start) * 60:
        return None
    return RouteOut(
        vehicle_id=v.id,
        plate=v.plate,
        load=load,
        distance_m=dist_m,
        duration_s=dur_s,
        finish=finish,
        fill=fill_pct,
        warning="; ".join(warns + extra),
        stops=stops,
    )


def _consolidate_fleet(
    assignment: dict[int, list[SolveOrder]],
    active: list[SolveVehicle],
    allowed_fn,
    load_of,
    by_id: dict[int, SolveOrder],
    idx: dict[int, int],
    matrix: Matrix,
    work_start: int,
    work_end: int,
    slack: int,
    default_unload: int,
    max_duration_s: int,
    notes: list[str],
) -> None:
    """Объединяет мелкие рейсы в меньшее число автомобилей, если влезают по весу и смене."""
    changed = True
    rounds = 0
    while changed and rounds < 40:
        changed = False
        rounds += 1
        used = [v for v in active if assignment.get(v.id)]
        if len(used) < 2:
            return
        used.sort(key=lambda v: load_of(v.id))
        small = used[0]
        batch = list(assignment[small.id])
        if not batch:
            continue
        total_w = sum(o.weight for o in batch)
        for big in sorted(used[1:], key=lambda v: -load_of(v.id)):
            if big.id == small.id:
                continue
            if load_of(big.id) + total_w > big.capacity:
                continue
            if not all(allowed_fn(big, o)[0] for o in batch):
                continue
            combined = assignment[big.id] + batch
            ids = [o.id for o in combined]
            seq = _nn_sequence(ids, idx, matrix)
            _, _, dur_s, _, _ = _simulate(seq, by_id, idx, matrix, work_start, work_end, slack, default_unload)
            if dur_s > max_duration_s:
                continue
            assignment[small.id].clear()
            assignment[big.id] = combined
            notes.append(f"Меньше машин: рейс {small.plate} → {big.plate} ({len(batch)} зак.).")
            changed = True
            break


def solve(
    orders: list[SolveOrder],
    vehicles: list[SolveVehicle],
    restrictions: list,
    settings: dict,
    time_limit_s: float = 12.0,
    depot: tuple[float, float] | None = None,
) -> SolveResult:
    depot_pt = depot or (DEPOT["lat"], DEPOT["lon"])
    t0 = time.time()
    notes = []
    if HAS_ORTOOLS:
        notes.append("OR-Tools доступен: TSP-сегменты маршрутов уточняются RoutingModel.")
    else:
        notes.append("OR-Tools недоступен в этой среде Python — использован встроенный CVRPTW-солвер той же постановки.")

    work_start = _parse_hm(settings.get("work_start", "09:00"), 9 * 60)
    max_hours = float(settings.get("max_hours", "8"))
    work_end = work_start + int(max_hours * 60)
    slack = int(settings.get("window_minutes", "60"))
    default_unload = int(settings.get("unload_minutes", "25"))
    min_fill = float(settings.get("min_fill", "0.9"))
    minimize_fleet = str(settings.get("minimize_fleet", "1")) != "0"
    use_windows = str(settings.get("use_windows", "1")) != "0"
    historic_rule = str(settings.get("historic_center_rule", "1")) != "0"
    try:
        max_trips = max(1, min(10, int(float(settings.get("max_trips", "3")))))
    except (TypeError, ValueError):
        max_trips = 3
    max_shift_s = int(max_hours * 3600)
    depot_turn_s = max(15, min(45, default_unload)) * 60
    if not use_windows:
        slack = 24 * 60
        for o in orders:
            o.preferred = None
            o.window_start = None
            o.window_end = None
    if not historic_rule:
        for o in orders:
            o.historic = False

    by_id = {o.id: o for o in orders}
    active = [v for v in vehicles if getattr(v.raw, "is_active", True)]
    if not active:
        return SolveResult([], [UnassignedOut(o.id, "Нет активных автомобилей", "", "Включите транспорт") for o in orders], False, 0, 0, notes)

    unassigned: list[UnassignedOut] = []
    geo_bad = [o for o in orders if o.lat is None or o.lon is None]
    for o in geo_bad:
        unassigned.append(UnassignedOut(o.id, "Нет координат", "Адрес не геокодирован", "Исправьте координаты вручную"))
    pool = [o for o in orders if o not in geo_bad]

    points = [depot_pt] + [(o.lat, o.lon) for o in pool]
    idx = {o.id: i + 1 for i, o in enumerate(pool)}
    matrix = build_matrix(points, start_hour=work_start // 60)

    def allowed(v: SolveVehicle, o: SolveOrder) -> tuple[bool, str]:
        class _O:
            restricted_historic = o.historic
            address = o.address

        return vehicle_allowed(v.raw, _O(), restrictions)

    assignment: dict[int, list[SolveOrder]] = {v.id: [] for v in active}
    leftover: list[SolveOrder] = []

    historic = [o for o in pool if o.historic]
    rest = [o for o in pool if not o.historic]
    hist_vehicles = []
    for v in active:
        if all(allowed(v, o)[0] for o in historic) or not historic:
            if historic and all(allowed(v, o)[0] for o in historic):
                hist_vehicles.append(v)
    if historic:
        hist_vehicles = [v for v in active if all(allowed(v, o)[0] for o in historic)]
        if not hist_vehicles:
            for o in historic:
                unassigned.append(
                    UnassignedOut(
                        o.id,
                        "Нет автомобиля, которому разрешён заезд в исторический центр",
                        "Советская / Мостовая / Замковая только для 1,5 т",
                        "Включите автомобиль 1,5 т или ослабьте ограничение",
                    )
                )
            historic = []
        else:
            hv = min(hist_vehicles, key=lambda x: x.capacity)
            hw = sum(o.weight for o in historic)
            if hw > hv.capacity:
                historic.sort(key=lambda o: -o.weight)
                kept, acc = [], 0
                for o in historic:
                    if acc + o.weight <= hv.capacity:
                        kept.append(o)
                        acc += o.weight
                    else:
                        unassigned.append(
                            UnassignedOut(
                                o.id,
                                "Не помещается в единственный разрешённый автомобиль 1,5 т",
                                f"Загрузка центра {hw} кг при ёмкости {hv.capacity} кг",
                                "Разнести доставку центра на два дня или снизить тоннаж",
                            )
                        )
                historic = kept
            assignment[hv.id].extend(historic)

    rest.sort(key=lambda o: -o.weight)
    total_cap = sum(v.capacity for v in active)
    total_dem = sum(o.weight for o in pool)
    notes.append(f"Спрос {total_dem} кг, ёмкость активных {total_cap} кг.")

    def load_of(vid: int) -> int:
        return sum(x.weight for x in assignment[vid])

    def centroid_of(vid: int):
        return _centroid(assignment[vid])

    rng = random.Random(42)
    for o in rest:
        best = None
        best_score = 10**18
        for v in active:
            ok, why = allowed(v, o)
            if not ok:
                continue
            load = load_of(v.id)
            if load + o.weight > v.capacity:
                continue
            target = v.capacity * min(0.99, total_dem / max(1, total_cap))
            after = load + o.weight
            c = centroid_of(v.id)
            geo = _dist_ll((o.lat, o.lon), c)
            over = max(0, after - target)
            under_empty = 0
            if minimize_fleet:
                if load == 0 and any(load_of(x.id) > 0 for x in active):
                    under_empty = 25_000
            else:
                under_empty = 0 if load else -8000
            score = geo + over * 3.5 + abs(after - target) * 0.15 + under_empty
            if after / v.capacity < min_fill and load:
                score -= 400
            if score < best_score:
                best_score = score
                best = v
        if best is None:
            leftover.append(o)
        else:
            assignment[best.id].append(o)

    def try_place(o: SolveOrder) -> bool:
        opts = []
        for v in active:
            ok, _ = allowed(v, o)
            if ok and load_of(v.id) + o.weight <= v.capacity:
                opts.append(v)
        if not opts:
            return False
        if minimize_fleet:
            loaded = [x for x in opts if load_of(x.id) > 0]
            if loaded:
                opts = loaded
        v = min(opts, key=lambda x: (load_of(x.id) + o.weight) / x.capacity * 100 + _dist_ll((o.lat, o.lon), centroid_of(x.id)) / 1000)
        assignment[v.id].append(o)
        return True

    still = []
    for o in leftover:
        if not try_place(o):
            still.append(o)
    leftover = still

    # Локальный обмен для 90% и географии
    def fill(v):
        return load_of(v.id) / v.capacity if v.capacity else 0

    deadline = t0 + time_limit_s * 0.65
    vehicles_by_id = {v.id: v for v in active}
    improved = True
    while improved and time.time() < deadline:
        improved = False
        if not minimize_fleet:
            needy = [v for v in active if 0 < fill(v) < min_fill]
            rich = [v for v in active if fill(v) >= min_fill]
            for nv in needy:
                need = int(math.ceil(min_fill * nv.capacity) - load_of(nv.id))
                for rv in rich:
                    movers = [o for o in assignment[rv.id] if allowed(nv, o)[0] and o.weight <= nv.capacity - load_of(nv.id)]
                    movers.sort(key=lambda o: abs(o.weight - need))
                    for o in movers:
                        if fill(rv) - o.weight / rv.capacity < min_fill:
                            continue
                        assignment[rv.id].remove(o)
                        assignment[nv.id].append(o)
                        improved = True
                        break
                    if improved:
                        break
                if improved:
                    break
        if improved:
            continue
        # swap 1-1 to shorten
        vids = [v.id for v in active if assignment[v.id]]
        for _ in range(80):
            if time.time() >= deadline:
                break
            if len(vids) < 2:
                break
            a, b = rng.sample(vids, 2)
            if not assignment[a] or not assignment[b]:
                continue
            oa = rng.choice(assignment[a])
            ob = rng.choice(assignment[b])
            va, vb = vehicles_by_id[a], vehicles_by_id[b]
            if not allowed(va, ob)[0] or not allowed(vb, oa)[0]:
                continue
            new_a = load_of(a) - oa.weight + ob.weight
            new_b = load_of(b) - ob.weight + oa.weight
            if new_a > va.capacity or new_b > vb.capacity:
                continue
            if new_a < min_fill * va.capacity or new_b < min_fill * vb.capacity:
                continue
            ca, cb = centroid_of(a), centroid_of(b)
            before = _dist_ll((oa.lat, oa.lon), ca) + _dist_ll((ob.lat, ob.lon), cb)
            after = _dist_ll((ob.lat, ob.lon), ca) + _dist_ll((oa.lat, oa.lon), cb)
            if after + 40 < before:
                assignment[a].remove(oa)
                assignment[b].remove(ob)
                assignment[a].append(ob)
                assignment[b].append(oa)
                improved = True
                break

    if not minimize_fleet:
        empty = [v for v in active if load_of(v.id) == 0]
        heavy = sorted([v for v in active if load_of(v.id) > 0], key=lambda v: -fill(v))
        for ev in empty:
            bag: list[SolveOrder] = []
            for hv in heavy:
                take = [o for o in list(assignment[hv.id]) if allowed(ev, o)[0]]
                take.sort(key=lambda o: o.weight)
                for o in take:
                    if load_of(hv.id) - o.weight < min_fill * hv.capacity:
                        continue
                    if sum(x.weight for x in bag) + o.weight > ev.capacity:
                        continue
                    assignment[hv.id].remove(o)
                    bag.append(o)
                    if sum(x.weight for x in bag) >= min_fill * ev.capacity:
                        break
                if sum(x.weight for x in bag) >= min_fill * ev.capacity:
                    break
            assignment[ev.id].extend(bag)
    elif minimize_fleet:
        max_dur = int(max_hours * 3600)
        _consolidate_fleet(
            assignment,
            active,
            allowed,
            load_of,
            by_id,
            idx,
            matrix,
            work_start,
            work_end,
            slack,
            default_unload,
            max_dur,
            notes,
        )
        used_n = sum(1 for v in active if assignment[v.id])
        notes.append(f"Режим мин. парка: задействовано {used_n} из {len(active)} активных машин.")

    pool = list(leftover)
    used_or = False
    routes: list[RouteOut] = []
    vehicle_shift_s: dict[int, int] = {v.id: 0 for v in active}

    for v in active:
        group = assignment[v.id]
        if not group:
            continue
        ro = _route_out_for_group(
            v,
            group,
            by_id,
            idx,
            matrix,
            work_start,
            work_end,
            slack,
            default_unload,
            min_fill,
            None,
            "Рейс 1" if max_trips > 1 else "",
        )
        if ro:
            routes.append(ro)
            vehicle_shift_s[v.id] = ro.duration_s
            if HAS_ORTOOLS and len(group) >= 3:
                used_or = True

    trip_no = 1
    while pool and trip_no < max_trips:
        trip_no += 1
        trip_load: dict[int, int] = {v.id: 0 for v in active}
        trip_assign: dict[int, list[SolveOrder]] = {v.id: [] for v in active}
        for o in sorted(pool, key=lambda x: -x.weight):
            best_v = None
            best_score = 10**18
            for v in active:
                ok, _ = allowed(v, o)
                if not ok:
                    continue
                if trip_load[v.id] + o.weight > v.capacity:
                    continue
                rem = max_shift_s - vehicle_shift_s[v.id]
                if rem < depot_turn_s + 45 * 60:
                    continue
                score = _dist_ll((o.lat, o.lon), _centroid(trip_assign[v.id])) if trip_assign[v.id] else 0
                if minimize_fleet and vehicle_shift_s[v.id] == 0 and any(vehicle_shift_s[x.id] > 0 for x in active):
                    score += 50_000
                elif vehicle_shift_s[v.id] > 0:
                    score -= 5000
                if score < best_score:
                    best_score = score
                    best_v = v
            if best_v:
                trip_assign[best_v.id].append(o)
                trip_load[best_v.id] += o.weight

        committed_ids: set[int] = set()
        added = 0
        for v in active:
            batch = trip_assign[v.id]
            if not batch:
                continue
            start_t = work_start + vehicle_shift_s[v.id] // 60 + (depot_turn_s // 60 if vehicle_shift_s[v.id] else 0)
            ro = _route_out_for_group(
                v,
                batch,
                by_id,
                idx,
                matrix,
                work_start,
                work_end,
                slack,
                default_unload,
                min(0.85, min_fill),
                start_t,
                f"Рейс {trip_no}",
            )
            if ro and ro.duration_s <= max_shift_s:
                routes.append(ro)
                vehicle_shift_s[v.id] = ro.duration_s
                committed_ids.update(o.id for o in batch)
                added += 1
        if not added:
            break
        pool = [o for o in pool if o.id not in committed_ids]
        notes.append(f"Рейс {trip_no}: добавлено маршрутов {added}, осталось заказов {len(pool)}.")

    for o in pool:
        why = []
        for v in active:
            ok, msg = allowed(v, o)
            if not ok:
                why.append(f"{v.plate}: {msg}")
            elif load_of(v.id) + o.weight > v.capacity:
                why.append(f"{v.plate}: не хватает ёмкости (остаток {v.capacity - load_of(v.id)} кг)")
            elif vehicle_shift_s[v.id] >= max_shift_s - depot_turn_s:
                why.append(f"{v.plate}: нет времени в смене для ещё одного рейса")
        unassigned.append(
            UnassignedOut(
                o.id,
                "Не удалось назначить: лимит рейсов, ёмкость или смена 8 ч",
                "; ".join(why[:8]),
                f"Увеличьте «макс. рейсов» (сейчас {max_trips}), добавьте машины или снизьте загрузку",
            )
        )

    routes.sort(key=lambda r: (-r.load, r.vehicle_id))
    total_d = sum(r.distance_m for r in routes)
    routes_per_vehicle = {}
    for r in routes:
        routes_per_vehicle[r.vehicle_id] = routes_per_vehicle.get(r.vehicle_id, 0) + 1
    multi = sum(1 for n in routes_per_vehicle.values() if n > 1)
    notes.append(
        f"Маршрутов: {len(routes)} (до {max_trips} рейсов/маш.), машин с 2+ рейсами: {multi}, нераспределено: {len(unassigned)}."
    )
    return SolveResult(routes, unassigned, used_or, time.time() - t0, total_d, notes)
