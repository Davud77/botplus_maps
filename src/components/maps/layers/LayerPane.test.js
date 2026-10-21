import React, { useEffect } from 'react';
import { render } from '@testing-library/react';
import { LayerPane } from './LayerPane';
const mockElement = document.createElement('div');
const mockMap = { getPane: () => mockElement };
jest.mock('react-leaflet', () => ({ Pane: ({ children }) => <>{children}</>, useMap: () => mockMap }));
test('opacity and order update the existing pane without remounting its tile source', () => {
  const mount = jest.fn(); const unmount = jest.fn();
  function TileSource() { useEffect(() => { mount(); return unmount; }, []); return null; }
  const view = render(<LayerPane name="roads" style={{ zIndex: 401, opacity: 1 }}><TileSource /></LayerPane>);
  view.rerender(<LayerPane name="roads" style={{ zIndex: 403, opacity: 0.35 }}><TileSource /></LayerPane>);
  expect(mockElement.style.zIndex).toBe('403');
  expect(mockElement.style.opacity).toBe('0.35');
  expect(mount).toHaveBeenCalledTimes(1);
  expect(unmount).not.toHaveBeenCalled();
});
