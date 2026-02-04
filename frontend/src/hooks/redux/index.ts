import { useDispatch, useSelector, type TypedUseSelectorHook } from 'react-redux'
import type { RootState, AppDispatch } from '../../store'

// Typed dispatch hook
export const useAppDispatch = () => useDispatch<AppDispatch>()

// Typed selector hook
export const useAppSelector: TypedUseSelectorHook<RootState> = useSelector
