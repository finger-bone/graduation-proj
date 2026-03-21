import { writable } from "svelte/store";

export function persistent<T>(key: string, initialValue: T) {
  let stored = initialValue;
  if (typeof localStorage !== 'undefined') {
    const json = localStorage.getItem(key);
    if (json != null) stored = JSON.parse(json);
  }
  const store = writable(stored);
  store.subscribe(v => {
    if (typeof localStorage !== 'undefined') {
      localStorage.setItem(key, JSON.stringify(v));
    }
  });
  return store;
}