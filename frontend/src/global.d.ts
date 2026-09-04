// Fallback ambient definitions for React, Vite, and JSX elements
declare namespace JSX {
  interface IntrinsicElements {
    [elemName: string]: any;
  }
}

declare namespace React {
  type ReactNode = any;
  type ComponentType<P = {}> = any;
  type FC<P = {}> = (props: P) => any;
  type FunctionComponent<P = {}> = (props: P) => any;
  type FormEvent<T = any> = any;
  type MouseEvent<T = any> = any;
  type ChangeEvent<T = any> = any;

  function useState<T>(initialState?: T | (() => T)): [T, (newState: T | ((prev: T) => T)) => void];
  function useEffect(effect: () => void | (() => void), deps?: any[]): void;
  function useCallback<T extends (...args: any[]) => any>(callback: T, deps: any[]): T;
  function useMemo<T>(factory: () => T, deps: any[]): T;
  function useRef<T>(initialValue?: T): { current: T };

  const StrictMode: any;
}

declare module 'react' {
  export = React;
}

declare module 'react-dom/client' {
  export const createRoot: any;
}

declare module 'react-dom' {
  export const render: any;
}

declare module 'vite' {
  export const defineConfig: any;
}

declare module '@vitejs/plugin-react' {
  const plugin: any;
  export default plugin;
}
