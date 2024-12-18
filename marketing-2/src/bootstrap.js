import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';

const mount = (el) => {
    const root = ReactDOM.createRoot(el);
    root.render(<App />);
}

// For Dev Mode
if (process.env.NODE_ENV === 'development') {
    const el = document.querySelector('#marketing-dev-root');
    if (el) {
        mount(el);
    }
}

export {mount};