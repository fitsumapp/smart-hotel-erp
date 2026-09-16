import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom'; 
import './index.css';
import App from './App';
import reportWebVitals from './reportWebVitals';
import { LoadingProvider } from './LoadingContext';


const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(
  <React.StrictMode>
    <BrowserRouter>
      {/* LoadingProvider hooks into all axios requests & shows overlay */}
      <LoadingProvider>
        <App />
      </LoadingProvider>
    </BrowserRouter>
  </React.StrictMode>
);

reportWebVitals();