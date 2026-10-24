import React from 'react';
import '@testing-library/jest-dom';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import Home from '../Home';
import ProfilePage from '../ProfilePage';
import { workspaceRequest } from '../../utils/workspaceApi';

let mockUser;
const mockNavigate = jest.fn();
const mockRefresh = jest.fn();
jest.mock('../../hooks/useAuth', () => ({ useAuth: () => ({ user: mockUser, logout: jest.fn(), refreshUser: mockRefresh }) }));
jest.mock('react-router-dom', () => ({ useNavigate: () => mockNavigate, useSearchParams: () => {const React=require('react');const [value,setValue]=React.useState(new URLSearchParams());return [value,next=>setValue(new URLSearchParams(next))];}, Link: ({ to, ...props }) => require('react').createElement('a', { href: to, ...props }) }), { virtual: true });
jest.mock('../Header', () => () => null);
jest.mock('../profile/ProfileVector', () => () => null);
jest.mock('../profile/ProfilePanoramas', () => () => null);
jest.mock('../profile/ProfileOrthophotos', () => () => null);
jest.mock('../../utils/workspaceApi', () => ({ ...jest.requireActual('../../utils/workspaceApi'), workspaceRequest: jest.fn() }));

beforeEach(() => {
  jest.clearAllMocks(); mockUser = { id: 1, username: 'owner', role: 'admin' };
  mockRefresh.mockResolvedValue(mockUser);
});

test('dashboard creates an actual map through the API and opens its document', async () => {
  workspaceRequest.mockImplementation((path, method) => Promise.resolve(method === 'POST' ? { map: { id: 'new-map' } } : { maps: [], total: 0 }));
  render(<Home />);
  fireEvent.click(screen.getByRole('button', { name: /Создать карту/ }));
  fireEvent.change(screen.getByLabelText('Название карты'), { target: { value: 'Site survey' } });
  fireEvent.click(screen.getByRole('button', { name: 'Создать и открыть' }));
  await waitFor(() => expect(mockNavigate).toHaveBeenCalledWith('/maps/new-map'));
  expect(workspaceRequest).toHaveBeenCalledWith('/maps','POST',{ title: 'Site survey', description: '' });
});

test('viewer sees existing maps but no user-management or map-creation controls', async () => {
  mockUser = { id: 3, username: 'observer', role: 'viewer' };
  workspaceRequest.mockResolvedValue({ maps: [{ id: 'saved', title: 'Existing map', description: 'Survey data', owner_name: 'owner', published: false, updated_at: '2026-10-21', can_edit: false }], total: 1 });
  const { unmount } = render(<Home />);
  await screen.findByRole('heading', { name: 'Existing map' });
  expect(screen.queryByRole('button', { name: /Создать карту/ })).toBeNull();
  expect(screen.getByRole('link', { name: /Открыть карту →/ }).getAttribute('href')).toBe('/maps/saved');
  unmount(); render(<ProfilePage />);
  expect(screen.queryByRole('button', { name: 'Пользователи' })).toBeNull();
  expect(screen.getAllByText('observer')).toHaveLength(2);
});

test('password confirmation prevents an accidental credential change', async () => {
  render(<ProfilePage />); fireEvent.click(screen.getByRole('button', { name: /Безопасность/ }));
  fireEvent.change(screen.getByLabelText('Текущий пароль'), { target: { value: 'current-password' } });
  fireEvent.change(screen.getByLabelText('Новый пароль', { exact: true }), { target: { value: 'new-test-password' } });
  fireEvent.change(screen.getByLabelText('Повторите новый пароль'), { target: { value: 'different-password' } });
  fireEvent.click(screen.getByRole('button', { name: 'Изменить пароль' }));
  expect(screen.getByRole('alert').textContent).toBe('Пароли не совпадают.');
  expect(workspaceRequest).not.toHaveBeenCalled();
});

test('administrator assigns a role through the protected API', async () => {
  workspaceRequest.mockImplementation((path, method) => Promise.resolve(method === 'PATCH'
    ? { user: { id: 2, username: 'teammate', role: 'editor', is_active: true } }
    : { users: [{ id: 2, username: 'teammate', role: 'viewer', is_active: true }] }));
  render(<ProfilePage />); fireEvent.click(screen.getByRole('button', { name: /Пользователи/ }));
  const select = await screen.findByLabelText('Роль teammate');
  fireEvent.change(select, { target: { value: 'editor' } });
  await waitFor(() => expect(workspaceRequest).toHaveBeenCalledWith('/users/2','PATCH',{ role: 'editor' }));
  await screen.findByText('Права пользователя обновлены.');
});

test('map cards keep editor and publication links without a rename action',async()=>{
 workspaceRequest.mockResolvedValue({maps:[{id:'saved',title:'Карта',description:'Описание',revision:4,can_edit:true,public_slug:'public-map',updated_at:'2026-10-23'}],total:1});
 render(<Home/>);await screen.findByRole('heading',{name:'Карта'});
 expect(screen.queryByRole('button',{name:'Переименовать'})).toBeNull();
 expect(screen.getByRole('link',{name:/Открыть редактор/})).toHaveAttribute('href','/maps/saved');
 expect(screen.getByRole('link',{name:/Публикация/})).toHaveAttribute('href','/p/public-map');
});
