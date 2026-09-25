import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import App from './App';

test('renders the sign-in screen', () => {
  render(<MemoryRouter><App /></MemoryRouter>);
  expect(screen.getByText(/welcome back/i)).toBeInTheDocument();
});
