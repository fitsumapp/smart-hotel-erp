import { apiErrorMessage } from './apiClient';

describe('apiErrorMessage parser', () => {
  it('extracts nested validation error messages from backend envelope', () => {
    const error = {
      response: {
        data: {
          error: 'Request could not be completed.',
          code: 'invalid',
          error_details: {
            code: 'invalid',
            message: 'Request could not be completed.',
            details: {
              name: ['inventory category with this name already exists.']
            }
          }
        }
      }
    };
    expect(apiErrorMessage(error)).toBe('Name: Inventory category with this name already exists.');
  });

  it('extracts error from direct details object', () => {
    const error = {
      response: {
        data: {
          error: {
            code: 'invalid',
            message: 'Request could not be completed.',
            details: {
              selling_price: ['Ensure this value is greater than or equal to 0.']
            }
          }
        }
      }
    };
    expect(apiErrorMessage(error)).toBe('Selling Price: Ensure this value is greater than or equal to 0.');
  });

  it('extracts non_field_errors without field prefix', () => {
    const error = {
      response: {
        data: {
          error: {
            code: 'invalid',
            message: 'Request could not be completed.',
            details: {
              non_field_errors: ['Invalid username or password combination.']
            }
          }
        }
      }
    };
    expect(apiErrorMessage(error)).toBe('Invalid username or password combination.');
  });

  it('falls back to string detail or fallback when no nested details exist', () => {
    const error = {
      response: {
        data: {
          detail: 'Unauthorized token.'
        }
      }
    };
    expect(apiErrorMessage(error)).toBe('Unauthorized token.');

    expect(apiErrorMessage(null, 'Custom fallback')).toBe('Custom fallback');
  });
});
