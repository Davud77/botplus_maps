// Minimal typings for 'lodash/debounce' deep import,
// чтобы не тянуть отдельные @types в образ.
declare module 'lodash/debounce' {
  export default function debounce<T extends (...args: any[]) => any>(
    func: T,
    wait?: number,
    options?: { leading?: boolean; trailing?: boolean; maxWait?: number }
  ): T & { cancel(): void; flush(): ReturnType<T> };
}
