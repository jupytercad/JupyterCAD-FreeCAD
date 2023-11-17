import {
  ICollaborativeDrive,
  SharedDocumentFactory
} from '@jupyter/docprovider';
import { IAnnotationModel, JupyterCadDoc } from '@jupytercad/schema';
import {
  JupyterFrontEnd,
  JupyterFrontEndPlugin
} from '@jupyterlab/application';
import {
  ICommandPalette,
  IThemeManager,
  showErrorMessage,
  WidgetTracker
} from '@jupyterlab/apputils';
import { IFileBrowserFactory } from '@jupyterlab/filebrowser';
import { ILauncher } from '@jupyterlab/launcher';
import { fileIcon } from '@jupyterlab/ui-components';

import { JupyterCadWidgetFactory } from '../factory';
import { IAnnotationToken, IJupyterCadDocTracker } from '../token';
import { requestAPI } from '../tools';
import { IJupyterCadWidget } from '../types';
import { JupyterCadFCModelFactory } from './modelfactory';

const FACTORY = 'Jupytercad Freecad Factory';

// const PALETTE_CATEGORY = 'JupyterCAD';

namespace CommandIDs {
  export const createNew = 'jupytercad:create-new-FCStd-file';
}

const activate = async (
  app: JupyterFrontEnd,
  tracker: WidgetTracker<IJupyterCadWidget>,
  themeManager: IThemeManager,
  annotationModel: IAnnotationModel,
  browserFactory: IFileBrowserFactory,
  drive: ICollaborativeDrive,
  launcher: ILauncher | null,
  palette: ICommandPalette | null
): Promise<void> => {
  const fcCheck = await requestAPI<{ installed: boolean }>(
    'cad/backend-check',
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
};

const fcplugin: JupyterFrontEndPlugin<void> = {
  id: 'jupytercad:fcplugin',
  requires: [
    IJupyterCadDocTracker,
    IThemeManager,
    IAnnotationToken,
    IFileBrowserFactory,
    ICollaborativeDrive
  ],
  optional: [ILauncher, ICommandPalette],
  autoStart: true,
  activate
};

export default fcplugin;
