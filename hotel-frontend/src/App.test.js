import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import App from './App';

beforeEach(() => {
  localStorage.clear();
});

test('renders the sign-in screen when unauthenticated', () => {
  render(
    <MemoryRouter initialEntries={['/']}>
      <App />
    </MemoryRouter>
  );
  expect(screen.getByText(/welcome back/i)).toBeInTheDocument();
});

test('routes housekeeping user to dedicated HousekeepingDashboard', () => {
  localStorage.setItem('access_token', 'valid-jwt-token');
  localStorage.setItem('user', JSON.stringify({
    id: 42,
    username: 'cleaner_sarah',
    role: 'housekeeping',
  }));

  render(
    <MemoryRouter initialEntries={['/dashboard']}>
      <App />
    </MemoryRouter>
  );

  expect(screen.getByText(/Housekeeping & Minibar Operations/i)).toBeInTheDocument();
  expect(screen.getByText('HOUSEKEEPING')).toBeInTheDocument();
  expect(screen.getByText(/cleaner_sarah/i)).toBeInTheDocument();
});

test('displays unauthorized fallback for unknown or unsupported roles', () => {
  localStorage.setItem('access_token', 'valid-jwt-token');
  localStorage.setItem('user', JSON.stringify({
    id: 99,
    username: 'unknown_alien',
    role: 'spaceship_captain',
  }));

  render(
    <MemoryRouter initialEntries={['/dashboard']}>
      <App />
    </MemoryRouter>
  );

  expect(screen.getByText(/Unauthorized/i)).toBeInTheDocument();
  expect(screen.getByRole('button', { name: /Back to Login/i })).toBeInTheDocument();
});
