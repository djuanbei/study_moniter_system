import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuth } from './auth.jsx'
import Layout from './components/Layout.jsx'
import Login from './pages/Login.jsx'
import Dashboard from './pages/Dashboard.jsx'
import Students from './pages/Students.jsx'
import Classes from './pages/Classes.jsx'
import QuestionWizard from './pages/QuestionWizard.jsx'
import Assignments from './pages/Assignments.jsx'
import DoAssignment from './pages/DoAssignment.jsx'
import ViewResult from './pages/ViewResult.jsx'
import Grading from './pages/Grading.jsx'
import Learning from './pages/Learning.jsx'
import Materials from './pages/Materials.jsx'
import Archive from './pages/Archive.jsx'
import Accounts from './pages/Accounts.jsx'
import SettingsPage from './pages/Settings.jsx'

function Protected({ children, teacherOnly = false }) {
  const { user, ready } = useAuth()
  if (!ready) return <div className="p-6 text-slate-500">加载中…</div>
  if (!user) return <Navigate to="/login" replace />
  if (teacherOnly && user.role !== 'teacher') return <Navigate to="/" replace />
  return children
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route element={<Protected><Layout /></Protected>}>
        <Route path="/" element={<Dashboard />} />
        <Route path="/students" element={<Protected teacherOnly><Students /></Protected>} />
        <Route path="/classes" element={<Protected teacherOnly><Classes /></Protected>} />
        <Route path="/wizard" element={<Protected teacherOnly><QuestionWizard /></Protected>} />
        <Route path="/learning" element={<Protected teacherOnly><Learning /></Protected>} />
        <Route path="/materials" element={<Protected teacherOnly><Materials /></Protected>} />
        <Route path="/assignments" element={<Assignments />} />
        <Route path="/assignments/:id/do" element={<DoAssignment />} />
        <Route path="/result/:id" element={<ViewResult />} />
        <Route path="/grading" element={<Protected teacherOnly><Grading /></Protected>} />
        <Route path="/grading/:submissionId" element={<Protected teacherOnly><Grading /></Protected>} />
        <Route path="/archive/:studentId" element={<Protected teacherOnly><Archive /></Protected>} />
        <Route path="/accounts" element={<Protected teacherOnly><Accounts /></Protected>} />
        <Route path="/settings" element={<Protected teacherOnly><SettingsPage /></Protected>} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  )
}