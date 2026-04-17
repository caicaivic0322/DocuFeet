import { DoctorWorkbench } from './pages/DoctorWorkbench'
import { ModelDashboard } from './pages/ModelDashboard'

function App() {
  const path = window.location.pathname

  if (path.startsWith('/models')) {
    return <ModelDashboard />
  }

  return <DoctorWorkbench />
}

export default App
