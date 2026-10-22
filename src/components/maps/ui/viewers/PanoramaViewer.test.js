import React from 'react';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import '@testing-library/jest-dom';
import Marzipano from 'marzipano';
import PanoramaViewer from './PanoramaViewer';

jest.mock('marzipano', () => ({
  Viewer: jest.fn(), EquirectGeometry: jest.fn(),
  ImageUrlSource: { fromString: jest.fn() },
  RectilinearView: Object.assign(jest.fn(), { limit: { traditional: jest.fn() } }),
}));
let mockViewer;
let mockTextureError;
function responses(media_type, width, height) {
  global.fetch = jest.fn().mockResolvedValueOnce({ ok: true, json: async () => ({ filename: 'ab/physical.jpg', display_name: 'GP123.JPG', width, height, media_type }) })
    .mockResolvedValueOnce({ ok: true, blob: async () => new Blob(['image']) });
}
beforeEach(() => {
  jest.clearAllMocks();
  URL.createObjectURL = jest.fn(() => 'blob:photo-test');
  URL.revokeObjectURL = jest.fn();
  mockTextureError = null;
  mockViewer = { createScene: jest.fn(() => ({ switchTo: jest.fn(), layer: () => ({ textureStore: () => ({ addEventListener: (_name, callback) => { mockTextureError = callback; } }) }) })), destroy: jest.fn(), updateSize: jest.fn() };
  Marzipano.Viewer.mockImplementation(() => mockViewer);
});

test('a 4:3 photograph uses a flat image and never creates a spherical renderer', async () => {
  responses('photo', 2704, 2028);
  const view = render(<PanoramaViewer markerId="1" isExpanded={false} />);
  expect(await screen.findByRole('img', { name: 'GP123.JPG' })).toHaveAttribute('src', 'blob:photo-test');
  expect(Marzipano.Viewer).not.toHaveBeenCalled();
  expect(screen.getByRole('button', { name: '360°' })).toBeDisabled();
  fireEvent.click(screen.getByRole('button', { name: 'Увеличить фото' }));
  expect(screen.getByRole('img')).toHaveStyle({ width: '150%' });
  view.unmount();
  expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:photo-test');
});

test('a real sphere uses its actual resolution and switches to photo without another download', async () => {
  responses('panorama', 5760, 2880);
  const view = render(<PanoramaViewer markerId="2" isExpanded={false} />);
  await waitFor(() => expect(Marzipano.Viewer).toHaveBeenCalledTimes(1));
  expect(Marzipano.EquirectGeometry).toHaveBeenCalledWith([{ width: 5760 }]);
  fireEvent.click(screen.getByRole('button', { name: 'Фото', exact: true }));
  expect(await screen.findByRole('img', { name: 'GP123.JPG' })).toBeInTheDocument();
  expect(mockViewer.destroy).toHaveBeenCalledTimes(1);
  expect(fetch).toHaveBeenCalledTimes(2);
  view.unmount();
  expect(URL.revokeObjectURL).toHaveBeenCalledTimes(1);
});

test('an unsuccessful download reports an error without creating a viewer', async () => {
  responses('photo', 2704, 2028);
  global.fetch.mockReset().mockResolvedValue({ ok: false, status: 404 });
  render(<PanoramaViewer markerId="3" isExpanded={false} />);
  expect(await screen.findByRole('alert')).toHaveTextContent('404');
  expect(Marzipano.Viewer).not.toHaveBeenCalled();
});

test('a texture failure is visible and the downloaded image remains available in photo mode', async () => {
  responses('panorama', 5760, 2880);
  render(<PanoramaViewer markerId="2" isExpanded={false} />);
  await waitFor(() => expect(mockTextureError).toBeInstanceOf(Function));
  act(() => mockTextureError(null, new Error('Texture unavailable')));
  expect(screen.getByRole('alert')).toHaveTextContent('Texture unavailable');
  fireEvent.click(screen.getByRole('button', { name: 'Фото', exact: true }));
  expect(await screen.findByRole('img', { name: 'GP123.JPG' })).toBeInTheDocument();
  expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  expect(fetch).toHaveBeenCalledTimes(2);
});
