import {useCallback, useEffect, useRef, useState} from 'react';
import {ApiError} from './api';

export interface Loaded<T> {data: T | null; error: ApiError | Error | null; loading: boolean; reload: () => void}

export function useLoad<T>(fn: () => Promise<T>, deps: unknown[], onAuth?: () => void): Loaded<T> {
  const [state, set] = useState<{data: T | null; error: Error | null; loading: boolean}>({data: null, error: null, loading: true});
  const seq = useRef(0);
  const run = useCallback(() => {
    const mine = ++seq.current;
    set(s => ({...s, loading: true, error: null}));
    fn().then(
      data => { if (mine === seq.current) set({data, error: null, loading: false}); },
      (error: Error) => {
        if (mine !== seq.current) return;
        if (error instanceof ApiError && error.status === 401) onAuth?.();
        set(s => ({data: s.data, error, loading: false}));
      },
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  useEffect(run, [run]);
  return {...state, reload: run};
}

export function useHashRoute(): [string, (to: string) => void] {
  const read = () => window.location.hash.replace(/^#/, '') || '/';
  const [route, set] = useState(read);
  useEffect(() => {
    const on = () => { set(read()); window.scrollTo(0, 0); };
    window.addEventListener('hashchange', on);
    return () => window.removeEventListener('hashchange', on);
  }, []);
  return [route, (to: string) => { window.location.hash = to; }];
}
