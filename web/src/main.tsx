import {StrictMode} from 'react';
import {createRoot} from 'react-dom/client';
import '@astryxdesign/core/reset.css';
import '@astryxdesign/core/astryx.css';
import '@astryxdesign/theme-neutral/theme.css';
import './styles.css';
import './app.css';
import App from './App';

createRoot(document.getElementById('root') as HTMLElement).render(<StrictMode><App /></StrictMode>);
