// plugins.ts
import { ICollaborativeDrive } from '@jupyter/collaborative-drive';
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
  InputDialog,
  showDialog,
  WidgetTracker
} from '@jupyterlab/apputils';
import { IMainMenu } from '@jupyterlab/mainmenu';
import { PathExt } from '@jupyterlab/coreutils';
import { LabIcon } from '@jupyterlab/ui-components';

import { JupyterCadWidgetFactory } from '@jupytercad/jupytercad-core';
import {
  IAnnotationToken,
  IJupyterCadDocTracker,
  IJupyterCadWidget
} from '@jupytercad/schema';
import { requestAPI } from '@jupytercad/base';
import { JupyterCadFCModelFactory } from './modelfactory';
import freecadIconSvg from '../style/freecad.svg';

const freecadIcon = new LabIcon({
  name: 'jupytercad:freecad',
  svgstr: freecadIconSvg
});

const FACTORY = 'Jupytercad Freecad Factory';
const EXPORT_FCSTD_CMD = 'jupytercad:export-fcstd';

export const fcplugin: JupyterFrontEndPlugin<void> = {
  id: 'jupytercad:fcplugin',
  requires: [
    IJupyterCadDocTracker,
    IMainMenu,
    IThemeManager,
    IAnnotationToken,
    ICollaborativeDrive,
    IJCadWorkerRegistryToken,
    IJCadExternalCommandRegistryToken
  ],
  autoStart: true,
  activate: async (
    app: JupyterFrontEnd,
    tracker: WidgetTracker<IJupyterCadWidget>,
    mainMenu: IMainMenu,
    themeManager: IThemeManager,
    annotationModel: IAnnotationModel,
    drive: ICollaborativeDrive,
    workerRegistry: IJCadWorkerRegistry,
    externalCommandRegistry: IJCadExternalCommandRegistry
  ) => {
    const { installed } = await requestAPI<{ installed: boolean }>(
      'jupytercad_freecad/backend-check',
      {
        method: 'POST',
        body: JSON.stringify({ backend: 'FreeCAD' })
      }
    );
    const backendCheck = () => {
      if (!installed) {
        showErrorMessage(
          'FreeCAD is not installed',
          'FreeCAD is required to open or export FCStd files'
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
    app.docRegistry.addWidgetFactory(widgetFactory);

    const modelFactory = new JupyterCadFCModelFactory({ annotationModel });
    app.docRegistry.addModelFactory(modelFactory);

    app.docRegistry.addFileType({
      name: 'FCStd',
      displayName: 'FCStd',
      mimeTypes: ['application/octet-stream'],
      extensions: ['.FCStd', '.fcstd'],
      fileFormat: 'base64',
      contentType: 'FCStd',
      icon: freecadIcon
    });

    drive.sharedModelFactory.registerDocumentFactory(
      'FCStd',
      (): JupyterCadDoc => new JupyterCadDoc()
    );

    widgetFactory.widgetCreated.connect((_, widget) => {
      widget.title.icon = freecadIcon;
      widget.context.pathChanged.connect(() => tracker.save(widget));
      themeManager.themeChanged.connect((_, changes) =>
        widget.context.model.themeChanged.emit(changes)
      );
      app.shell.activateById('jupytercad::leftControlPanel');
      app.shell.activateById('jupytercad::rightControlPanel');
      tracker.add(widget);
    });

    console.log('jupytercad:fcplugin is activated!');

    app.commands.addCommand(EXPORT_FCSTD_CMD, {
      label: 'Export to .FCStd',
      iconClass: 'fa fa-file-export',
      isEnabled: () => {
        const w = tracker.currentWidget;
        return !!w && w.context.path.toLowerCase().endsWith('.jcad');
      },
      execute: async () => {
        const w = tracker.currentWidget;
        if (!w) {
          return;
        }
        const defaultName = PathExt.basename(w.context.path).replace(
          /\.[^.]+$/,
          '.FCStd'
        );
        const result = await InputDialog.getText({
          title: 'Export to .FCStd',
          placeholder: 'Output file name',
          text: defaultName
        });
        if (!result.value) {
          return;
        }
        try {
          const resp = await requestAPI<{ path?: string; done?: boolean }>(
            'jupytercad_freecad/export-fcstd',
            {
              method: 'POST',
              body: JSON.stringify({
                path: w.context.path,
                newName: result.value
              })
            }
          );
          const outPath = resp.path ?? result.value;
          await showDialog({
            title: 'Export successful',
            body: `Wrote file to: ${outPath}`
          });
        } catch (e: any) {
          showErrorMessage('Export Error', e.message || String(e));
        }
      }
    });

    mainMenu.fileMenu.addGroup([{ command: EXPORT_FCSTD_CMD }], /* rank */ 100);
  }
};

export default [fcplugin];
