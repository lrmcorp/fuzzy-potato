// Phone notifications (Web Push) for this device: state, turn on, turn off, test.
import {api} from './api';

export type PushState = 'checking' | 'unsupported' | 'ios-home' | 'denied' | 'off' | 'on';

const isIos = () => /iphone|ipad|ipod/i.test(navigator.userAgent);
const standalone = () => window.matchMedia('(display-mode: standalone)').matches || (navigator as {standalone?: boolean}).standalone === true;

function keyBytes(b64: string): Uint8Array {
  const pad = '='.repeat((4 - (b64.length % 4)) % 4);
  const raw = atob((b64 + pad).replace(/-/g, '+').replace(/_/g, '/'));
  return Uint8Array.from(raw, c => c.charCodeAt(0));
}

const registration = () => navigator.serviceWorker.register('/sw.js');

export async function pushState(): Promise<PushState> {
  try {
    if (!('serviceWorker' in navigator) || !('PushManager' in window) || !('Notification' in window)) {
      return isIos() && !standalone() ? 'ios-home' : 'unsupported';
    }
    if (Notification.permission === 'denied') return 'denied';
    const reg = await registration();
    return (await reg.pushManager.getSubscription()) ? 'on' : 'off';
  } catch {
    return 'unsupported';
  }
}

export async function enablePush(): Promise<PushState> {
  const perm = await Notification.requestPermission();
  if (perm !== 'granted') return perm === 'denied' ? 'denied' : 'off';
  const reg = await registration();
  const {key} = await api.pushInfo();
  const sub = await reg.pushManager.subscribe({userVisibleOnly: true, applicationServerKey: keyBytes(key) as BufferSource});
  await api.pushSubscribe(sub.toJSON());
  return 'on';
}

export async function disablePush(): Promise<PushState> {
  const sub = await (await registration()).pushManager.getSubscription();
  if (sub) { await api.pushUnsubscribe(sub.endpoint); await sub.unsubscribe(); }
  return 'off';
}
