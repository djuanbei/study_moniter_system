import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth.jsx'

const NAV = [
  { to: '/', label: '工作台', icon: '🏠' },
  { to: '/assignments', label: '我的作业', icon: '📝', student: true },
  { to: '/exams', label: '在线考试', icon: '🎯' },
  { to: '/learning', label: '学习闭环', icon: '🔄', teacher: true },
  { to: '/materials', label: '教材资料', icon: '📚', teacher: true },
  { to: '/history', label: '历史试卷', icon: '🗂️', teacher: true },
  { to: '/wizard', label: '出题向导', icon: '✨', teacher: true },
  { to: '/question-bank', label: '题库', icon: '🏦', teacher: true },
  { to: '/grading', label: '批改', icon: '✅', teacher: true },
  { to: '/students', label: '学生管理', icon: '🧒', teacher: true },
  { to: '/classes', label: '班级管理', icon: '🏫', teacher: true },
  { to: '/accounts', label: '账号管理', icon: '👥', teacher: true },
  { to: '/settings', label: '系统设置', icon: '⚙️', teacher: true },
]

export default function Layout() {
  const { user, logout, mustChange } = useAuth()
  const nav = useNavigate()

  async function onLogout() {
    await logout()
    nav('/login')
  }

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark">学</span>
          <div>
            <div className="brand-title">学习陪伴</div>
            <div className="brand-sub">Learning Companion</div>
          </div>
        </div>
        <nav>
          {NAV.filter(n => {
            if (n.teacher && user?.role !== 'teacher') return false
            if (n.student && user?.role !== 'student') return false
            return true
          }).map((n) => (
            <NavLink key={n.to} to={n.to} end={n.to === '/'} className={({ isActive }) => 'nav-item' + (isActive ? ' active' : '')}>
              <span className="nav-icon">{n.icon}</span>
              <span>{n.label}</span>
            </NavLink>
          ))}
        </nav>
      </aside>
      <main className="main">
        <header className="topbar">
          <div className="topbar-title">学习陪伴系统</div>
          <div className="topbar-user">
            {mustChange && <span className="badge-warn">请修改初始密码</span>}
            <span className="user-name">{user?.display_name || user?.username}</span>
            <span className="user-role">{user?.role === 'teacher' ? '教师' : '学生'}</span>
            <button className="btn-ghost" onClick={onLogout}>退出登录</button>
          </div>
        </header>
        <div className="content">
          <Outlet />
        </div>
      </main>
    </div>
  )
}