import {
  ICollaborativeDrive,
  SharedDocumentFactory
} from '@jupyter/docprovider';
import {
  IAnnotationModel,
  IJCadWorkerRegistry,
  JupyterCadDoc,
  IJCadWorkerRegistryToken,
  IJCadExternalCommandRegistry,
  IJCadExternalCommandRegistryToken
} from '@jupytercad/schema';
import {
  JupyterFrontEnd,
  JupyterFrontEndPlugin
} from '@jupyterlab/application';
import {
  IThemeManager,
  showErrorMessage,
  WidgetTracker
} from '@jupyterlab/apputils';

import { JupyterCadWidgetFactory } from '@jupytercad/jupytercad-core';
import {
  IAnnotationToken,
  IJupyterCadDocTracker,
  IJupyterCadWidget
} from '@jupytercad/schema';
import { requestAPI } from '@jupytercad/base';
import { JupyterCadFCModelFactory } from './modelfactory';

const FACTORY = 'Jupytercad Freecad Factory';

const activate = async (
  app: JupyterFrontEnd,
  tracker: WidgetTracker<IJupyterCadWidget>,
  themeManager: IThemeManager,
  annotationModel: IAnnotationModel,
  drive: ICollaborativeDrive,
  workerRegistry: IJCadWorkerRegistry,
  externalCommandRegistry: IJCadExternalCommandRegistry
): Promise<void> => {
  const fcCheck = await requestAPI<{ installed: boolean }>(
    'jupytercad_freecad/backend-check',
    {
      method: 'POST',
      body: JSON.stringify({
        backend: 'FreeCAD'
      })
    }
  );
  const { installed } = fcCheck;
  const backendCheck = () => {
    if (!installed) {
      showErrorMessage(
        'FreeCAD is not installed',
        'FreeCAD is required to open FCStd files'
      );
    }
    return installed;
  };
  const widgetFactory = new JupyterCadWidgetFactory({
    name: FACTORY,
    modelName: 'jupytercad-fcmodel',
    fileTypes: ['FCStd'],
    defaultFor: ['FCStd'],
    tracker,
    commands: app.commands,
    workerRegistry,
    externalCommandRegistry,
    backendCheck
  });

  // Registering the widget factory
  app.docRegistry.addWidgetFactory(widgetFactory);

  // Creating and registering the model factory for our custom DocumentModel
  const modelFactory = new JupyterCadFCModelFactory({ annotationModel });
  app.docRegistry.addModelFactory(modelFactory);
  // register the filetype
  app.docRegistry.addFileType({
    name: 'FCStd',
    displayName: 'FCStd',
    mimeTypes: ['application/octet-stream'],
    extensions: ['.FCStd', 'fcstd'],
    fileFormat: 'base64',
    contentType: 'FCStd'
  });

  const FCStdSharedModelFactory: SharedDocumentFactory = () => {
    return new JupyterCadDoc();
  };
  drive.sharedModelFactory.registerDocumentFactory(
    'FCStd',
    FCStdSharedModelFactory
  );

  widgetFactory.widgetCreated.connect((sender, widget) => {
    // Notify the instance tracker if restore data needs to update.
    widget.context.pathChanged.connect(() => {
      tracker.save(widget);
    });
    themeManager.themeChanged.connect((_, changes) =>
      widget.context.model.themeChanged.emit(changes)
    );

    tracker.add(widget);
    app.shell.activateById('jupytercad::leftControlPanel');
    app.shell.activateById('jupytercad::rightControlPanel');
  });
  console.log('jupytercad:fcplugin is activated!');
};

export const fcplugin: JupyterFrontEndPlugin<void> = {
  id: 'jupytercad:fcplugin',
  requires: [
    IJupyterCadDocTracker,
    IThemeManager,
    IAnnotationToken,
    ICollaborativeDrive,
    IJCadWorkerRegistryToken,
    IJCadExternalCommandRegistryToken
  ],
  autoStart: true,
  activate
};
