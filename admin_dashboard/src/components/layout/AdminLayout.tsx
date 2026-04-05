import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useAuth } from '@/contexts/AuthContext'
import clsx from 'clsx'

const NAV_ITEMS = [
  { to: '/dashboard', label: 'Dashboard', icon: '▦' },
  { to: '/symbols', label: 'Symbols', icon: '◈' },
  { to: '/pools', label: 'Pools', icon: '◎' },
  { to: '/users', label: 'Users', icon: '◉' },
  { to: '/settings', label: 'Settings', icon: '⚙' },
  { to: '/audit-log', label: 'Audit Log', icon: '▤' },
]

export function AdminLayout() {
  const { admin, logout } = useAuth()
  const navigate = useNavigate()

  const handleLogout = async () => {
    await logout()
    navigate('/login', { replace: true })
  }

  return (
    <div className="flex min-h-screen bg-bg-primary">
      {/* Sidebar */}
      <aside className="w-56 flex flex-col border-r border-border-default bg-bg-secondary">
        {/* Logo */}
        <div className="px-5 py-5 border-b border-border-default">
          <h1 className="text-sm font-semibold text-text-primary tracking-wide">VEGA ADMIN</h1>
        </div>

        {/* Navigation */}
        <nav className="flex-1 py-3 px-3 space-y-0.5">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                clsx(
                  'flex items-center gap-3 px-3 py-2 rounded-md text-sm transition-colors',
                  isActive
                    ? 'bg-bg-hover text-text-primary'
                    : 'text-text-secondary hover:text-text-primary hover:bg-bg-hover/50'
                )
              }
            >
              <span className="text-xs">{item.icon}</span>
              {item.label}
            </NavLink>
          ))}
        </nav>

        {/* Admin profile */}
        <div className="px-3 py-4 border-t border-border-default">
          <div className="flex items-center gap-3 px-2">
            {admin?.photo_url ? (
              <img
                src={admin.photo_url}
                alt=""
                className="w-7 h-7 rounded-full"
              />
            ) : (
              <div className="w-7 h-7 rounded-full bg-bg-hover flex items-center justify-center text-xs text-text-secondary">
                {admin?.name?.[0] || '?'}
              </div>
            )}
            <div className="flex-1 min-w-0">
              <p className="text-xs text-text-primary truncate">{admin?.name}</p>
              <p className="text-xs text-text-tertiary truncate">{admin?.role}</p>
            </div>
          </div>
          <button
            onClick={handleLogout}
            className="w-full mt-3 px-3 py-1.5 text-xs text-text-secondary hover:text-text-primary hover:bg-bg-hover rounded-md transition-colors"
          >
            Sign out
          </button>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 flex flex-col">
        <div className="flex-1 p-6">
          <Outlet />
        </div>
      </main>
    </div>
  )
}
