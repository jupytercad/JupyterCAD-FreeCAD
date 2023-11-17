import {
  JupyterFrontEnd,
  JupyterFrontEndPlugin
} from '@jupyterlab/application';

/**
 * Initialization data for the @jupytercad/jupytercad-freecad extension.
 */
const plugin: JupyterFrontEndPlugin<void> = {
  id: '@jupytercad/jupytercad-freecad:plugin',
  description: 'A JupyterLab extension.',
  autoStart: true,
  activate: (app: JupyterFrontEnd) => {
    console.log('JupyterLab extension @jupytercad/jupytercad-freecad is activated!');
  }
};

export default plugin;
