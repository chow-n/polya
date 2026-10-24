import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import 'katex/dist/katex.min.css';
import './styles.css';
import './polya.css';
import App from './App';
import { initTheme } from './store/prefs';

const root = document.getElementById('root');
if (!root) throw new Error('#root missing from index.html');

initTheme();
document.title = 'Pólya';

createRoot(root).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
