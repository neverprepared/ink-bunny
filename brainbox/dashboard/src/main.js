import App from './App.svelte';
import { mount } from 'svelte';
import { initApiKey } from './lib/api.js';

await initApiKey();

const app = mount(App, { target: document.getElementById('app') });

export default app;
