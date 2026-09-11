import { useEffect, useState } from 'react'

export function usePlaybook() {
  const [playbook, setPlaybook] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const refresh = async () => {
    setLoading(true); setError(null)
    try {
      const r = await fetch('/api/playbook')
      setPlaybook(await r.json())
    } catch (e) {
      setError(String(e))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { refresh() }, [])

  return { playbook, loading, error, refresh }
}
