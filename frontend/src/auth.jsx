import { createContext, useContext, useEffect, useState } from 'react'
import { endpoints } from './api.js'

const Ctx = createContext({ user: null, ready: false, refresh: () => {}, logout: () => {} })

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [mustChange, setMustChange] = useState(false)
  const [ready, setReady] = useState(false)

  async function refresh() {
    try {
      const data = await endpoints.bootstrap()
      setUser(data.user)
      setMustChange(data.must_change_password)
    } catch {
      setUser(null)
    } finally {
      setReady(true)
    }
  }

  useEffect(() => {
    refresh()
  }, [])

  async function logout() {
    try { await endpoints.logout() } catch {}
    setUser(null)
    setMustChange(false)
  }

  return (
    <Ctx.Provider value={{ user, mustChange, ready, refresh, logout }}>
      {children}
    </Ctx.Provider>
  )
}

export function useAuth() {
  return useContext(Ctx)
}