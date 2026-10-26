import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import axios from 'axios';
import ReportsCenter from './ReportsCenter';

jest.mock('axios');

describe('ReportsCenter — DEFECT-OPS-001 Z-Report preview vs close separation', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('generates Z-Report preview via GET and does not invoke POST closure', async () => {
    axios.get.mockResolvedValueOnce({
      data: {
        report_type: 'Z-Report (Preview)',
        date: '2026-10-26',
        is_closed: false,
        closed_by: null,
        closed_at: null,
        grand_total: 1500,
        restaurant: { cash: 500, total: 500, order_count: 2 },
        rooms: { revenue: 1000, cash: 1000, checkouts: 1 },
      },
    });

    render(<ReportsCenter initialTab="zreport" />);

    const previewBtn = screen.getByRole('button', { name: /preview z-report/i });
    expect(previewBtn).toBeInTheDocument();

    fireEvent.click(previewBtn);

    await waitFor(() => {
      expect(axios.get).toHaveBeenCalledWith(expect.stringContaining('/users/reports/z-report/'));
    });

    // Verify axios.post was NOT called on preview
    expect(axios.post).not.toHaveBeenCalled();

    // Verify Open warning banner is displayed
    expect(await screen.findByText(/Day Preview \(Open\)/i)).toBeInTheDocument();
    expect(screen.getByText(/previewing figures does not close or lock registers/i)).toBeInTheDocument();

    // Verify the explicit close button is rendered
    expect(screen.getAllByRole('button', { name: /close business day/i }).length).toBeGreaterThan(0);
  });

  it('requires explicit confirmation before calling POST to close business day', async () => {
    axios.get.mockResolvedValueOnce({
      data: {
        report_type: 'Z-Report (Preview)',
        date: '2026-10-26',
        is_closed: false,
        grand_total: 2000,
        restaurant: { cash: 1000, total: 1000, order_count: 3 },
        rooms: { revenue: 1000, cash: 1000, checkouts: 1 },
      },
    });

    axios.post.mockResolvedValueOnce({
      data: {
        report_type: 'Z-Report',
        date: '2026-10-26',
        is_closed: true,
        closed_by: 'fin_officer',
        closed_at: '2026-10-26T22:00:00Z',
        grand_total: 2000,
        restaurant: { cash: 1000, total: 1000, order_count: 3 },
        rooms: { revenue: 1000, cash: 1000, checkouts: 1 },
      },
    });

    render(<ReportsCenter initialTab="zreport" />);

    fireEvent.click(screen.getByRole('button', { name: /preview z-report/i }));

    const closeBtn = await screen.findByRole('button', { name: /close business day \(z-report\)/i });
    fireEvent.click(closeBtn);

    // Modal should now be open
    expect(screen.getByText(/Confirm Business Day Closure/i)).toBeInTheDocument();
    expect(axios.post).not.toHaveBeenCalled();

    // Confirm inside modal
    const confirmBtn = screen.getByRole('button', { name: /confirm & close day/i });
    fireEvent.click(confirmBtn);

    await waitFor(() => {
      expect(axios.post).toHaveBeenCalledWith(
        expect.stringContaining('/users/reports/z-report/'),
        expect.objectContaining({ date: expect.any(String) })
      );
    });

    // Finalized banner should appear
    expect(await screen.findByText(/Z-Report closed & finalized/i)).toBeInTheDocument();
  });
});
