import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import SetupPage from './SetupPage';

const mockCompleteSetup = jest.fn();
const mockNavigate = jest.fn();
jest.mock('../hooks/useAuth', () => ({ useAuth: () => ({ completeSetup: mockCompleteSetup }) }));
jest.mock('react-router-dom', () => ({ useNavigate: () => mockNavigate }), { virtual: true });

function fill(confirmation = 'a-very-long-password') {
  fireEvent.change(screen.getByLabelText('Логин администратора'), { target: { value: 'davud' } });
  fireEvent.change(screen.getByLabelText('Пароль'), { target: { value: 'a-very-long-password' } });
  fireEvent.change(screen.getByLabelText('Повторите пароль'), { target: { value: confirmation } });
  fireEvent.click(screen.getByRole('button', { name: /Создать аккаунт/ }));
}

beforeEach(() => { jest.clearAllMocks(); global.fetch = jest.fn(); });

test('mismatched passwords stay local and show an accessible error', () => {
  render(<SetupPage />); fill('different-long-password');
  expect(screen.getByRole('alert').textContent).toBe('Пароли не совпадают.');
  expect(fetch).not.toHaveBeenCalled();
});

test('successful enrollment opens the authenticated app', async () => {
  fetch.mockResolvedValue({ ok: true, status: 201, json: async () => ({ status: 'ok' }) });
  render(<SetupPage />); fill();
  await waitFor(() => expect(mockCompleteSetup).toHaveBeenCalledTimes(1));
  expect(mockNavigate).toHaveBeenCalledWith('/', { replace: true });
  expect(fetch).toHaveBeenCalledWith('/api/setup/initialize', expect.objectContaining({ credentials: 'include', method: 'POST' }));
});

test('a completed concurrent setup offers login and does not authenticate', async () => {
  fetch.mockResolvedValue({ ok: false, status: 409, json: async () => ({ message: 'Настройка уже завершена.' }) });
  render(<SetupPage />); fill();
  await waitFor(() => expect(screen.getByRole('alert').textContent).toBe('Настройка уже завершена.'));
  expect(screen.getByRole('link', { name: /Перейти ко входу/ }).getAttribute('href')).toBe('/login');
  expect(mockCompleteSetup).not.toHaveBeenCalled();
});
