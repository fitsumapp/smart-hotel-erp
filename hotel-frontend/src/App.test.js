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

test('deduplicates user badge when username and role are identical (e.g. finance/finance)', () => {
  localStorage.setItem('access_token', 'valid-jwt-token');
  localStorage.setItem('user', JSON.stringify({
    id: 10,
    username: 'finance',
    role: 'finance',
  }));

  render(
    <MemoryRouter initialEntries={['/dashboard']}>
      <App />
    </MemoryRouter>
  );

  // Capitalized primary name is present
  expect(screen.getByText('Finance')).toBeInTheDocument();
  // Instead of redundant "FINANCE" stacked under "finance", clean distinct subtitle is rendered
  expect(screen.getByText('HOTEL STAFF')).toBeInTheDocument();
  // Avatar initial 'F'
  expect(screen.getByText('F')).toBeInTheDocument();
});

test('displays full name and role when user profile has distinct first/last name', () => {
  localStorage.setItem('access_token', 'valid-jwt-token');
  localStorage.setItem('user', JSON.stringify({
    id: 11,
    username: 'jdoe',
    first_name: 'John',
    last_name: 'Doe',
    role: 'finance',
  }));

  render(
    <MemoryRouter initialEntries={['/dashboard']}>
      <App />
    </MemoryRouter>
  );

  expect(screen.getByText('John Doe')).toBeInTheDocument();
  expect(screen.getByText('FINANCE')).toBeInTheDocument();
  expect(screen.getByText('J')).toBeInTheDocument();
});
