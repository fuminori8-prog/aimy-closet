import {
  useCallback,
  useEffect,
  useMemo,
  useState,
} from 'react'
import {
  onAuthStateChanged,
  signInAnonymously,
} from 'firebase/auth'
import {
  collection,
  doc,
  onSnapshot,
  runTransaction,
  serverTimestamp,
} from 'firebase/firestore'
import { auth, db } from '../firebase'
import FavoritesContext from './favoritesContext'

let anonymousSignInPromise = null

const ensureAnonymousUser = async () => {
  if (auth.currentUser) {
    return auth.currentUser
  }

  if (!anonymousSignInPromise) {
    anonymousSignInPromise = signInAnonymously(auth)
      .then((credential) => credential.user)
      .finally(() => {
        anonymousSignInPromise = null
      })
  }

  return anonymousSignInPromise
}

export function FavoritesProvider({ children }) {
  const [user, setUser] = useState(auth.currentUser)
  const [favoriteIds, setFavoriteIds] = useState(() => new Set())
  const [counts, setCounts] = useState({})
  const [authLoading, setAuthLoading] = useState(true)
  const [busyItemIds, setBusyItemIds] = useState(() => new Set())
  const [error, setError] = useState('')

  useEffect(() => {
    const unsubscribe = onAuthStateChanged(auth, async (currentUser) => {
      if (currentUser) {
        setUser(currentUser)
        setAuthLoading(false)
        return
      }

      try {
        const anonymousUser = await ensureAnonymousUser()
        setUser(anonymousUser)
      } catch (authError) {
        console.error(authError)
        setError('お気に入り機能を開始できませんでした。')
      } finally {
        setAuthLoading(false)
      }
    })

    return unsubscribe
  }, [])

  useEffect(() => {
    const countsRef = collection(db, 'itemFavoriteCounts')

    return onSnapshot(
      countsRef,
      (snapshot) => {
        const nextCounts = {}

        snapshot.forEach((countDoc) => {
          const value = Number(countDoc.data()?.favoriteCount || 0)
          nextCounts[countDoc.id] = Math.max(0, value)
        })

        setCounts(nextCounts)
      },
      (snapshotError) => {
        console.error(snapshotError)
        setError('お気に入り数を読み込めませんでした。')
      },
    )
  }, [])

  useEffect(() => {
    if (!user) {
      setFavoriteIds(new Set())
      return undefined
    }

    const favoritesRef = collection(db, 'users', user.uid, 'favorites')

    return onSnapshot(
      favoritesRef,
      (snapshot) => {
        setFavoriteIds(new Set(snapshot.docs.map((favoriteDoc) => favoriteDoc.id)))
      },
      (snapshotError) => {
        console.error(snapshotError)
        setError('お気に入り一覧を読み込めませんでした。')
      },
    )
  }, [user])

  const toggleFavorite = useCallback(
    async (itemId) => {
      if (!itemId || busyItemIds.has(itemId)) {
        return
      }

      setError('')
      setBusyItemIds((current) => new Set(current).add(itemId))

      try {
        const activeUser = user || (await ensureAnonymousUser())
        const favoriteRef = doc(db, 'users', activeUser.uid, 'favorites', itemId)
        const countRef = doc(db, 'itemFavoriteCounts', itemId)

        await runTransaction(db, async (transaction) => {
          const favoriteSnapshot = await transaction.get(favoriteRef)
          const countSnapshot = await transaction.get(countRef)
          const currentCount = Math.max(
            0,
            Number(countSnapshot.data()?.favoriteCount || 0),
          )

          if (favoriteSnapshot.exists()) {
            transaction.delete(favoriteRef)
            transaction.set(countRef, {
              favoriteCount: Math.max(0, currentCount - 1),
              updatedAt: serverTimestamp(),
            })
          } else {
            transaction.set(favoriteRef, {
              itemId,
              createdAt: serverTimestamp(),
            })
            transaction.set(countRef, {
              favoriteCount: currentCount + 1,
              updatedAt: serverTimestamp(),
            })
          }
        })
      } catch (toggleError) {
        console.error(toggleError)
        setError('お気に入りを更新できませんでした。もう一度お試しください。')
      } finally {
        setBusyItemIds((current) => {
          const next = new Set(current)
          next.delete(itemId)
          return next
        })
      }
    },
    [busyItemIds, user],
  )

  const value = useMemo(
    () => ({
      authLoading,
      counts,
      error,
      favoriteIds,
      isFavorite: (itemId) => favoriteIds.has(itemId),
      isBusy: (itemId) => busyItemIds.has(itemId),
      toggleFavorite,
    }),
    [authLoading, busyItemIds, counts, error, favoriteIds, toggleFavorite],
  )

  return (
    <FavoritesContext.Provider value={value}>
      {children}
    </FavoritesContext.Provider>
  )
}
