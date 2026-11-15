import DriverApp from '../driver/DriverApp'

export default function Driver({ onLogout }: { onLogout?: () => void }) {
  return <DriverApp onLogout={onLogout} />
}
