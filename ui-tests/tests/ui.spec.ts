import { expect, test, galata } from '@jupyterlab/galata';
import path from 'path';

test.use({ autoGoto: false });

test.describe('UI Test', () => {
  const fileList = [
    'example_2D.FCStd',
    'example1.FCStd',
    'example2.FCStd',
    'example3.FCStd',
    'example4.FCStd',
    'example5.FCStd',
    'example6.FCStd',
    'common.FCStd',
    'cut.FCStd'
  ];

  test.describe('Extension activation test', () => {
    test('should emit an activation console message', async ({
      page,
      request
    }) => {
      const logs: string[] = [];

      page.on('console', message => {
        logs.push(message.text());
      });

      await page.goto();

      expect(
        logs.filter(s => s === 'jupytercad:fcplugin is activated!')
      ).toHaveLength(1);
    });
  });

  test.describe('File rendering test', () => {
    test.beforeAll(async ({ request }) => {
      const content = galata.newContentsHelper(request);
      await content.deleteDirectory('/examples');
      await content.uploadDirectory(
        path.resolve(__dirname, '../../examples'),
        '/examples'
      );
    });
    let errors = 0;
    test.beforeEach(async ({ page }) => {
      page.setViewportSize({ width: 1920, height: 1080 });
      page.on('console', message => {
        if (message.type() === 'error') {
          errors += 1;
        }
      });
    });

    test.afterEach(async ({ page }) => {
      errors = 0;
    });

    for (const file of fileList) {
      test(`Should be able to render ${file} without error`, async ({
        page
      }) => {
        await page.goto();
        const fullPath = `examples/${file}`;
        await page.notebook.openByPath(fullPath);
        await page.notebook.activate(fullPath);
        await page.locator('div.jpcad-Spinner').waitFor({ state: 'hidden' });

        await page
          .getByRole('tablist', { name: 'main sidebar' })
          .getByRole('tab', { name: 'JupyterCad Control Panel' })
          .click();
        await page
          .getByRole('tablist', { name: 'alternate sidebar' })
          .getByRole('tab', { name: 'JupyterCad Control Panel' })
          .click();
        await page.waitForTimeout(1000);
        const main = await page.$('#jp-main-split-panel');
        expect(errors).toBe(0);
        if (main) {
          expect(await main.screenshot()).toMatchSnapshot({
            name: `Render-${file}.png`,
            maxDiffPixelRatio: 0.01
          });
        }
      });
    }
  });

  test.describe('File operator test', () => {
    let errors = 0;
    test.beforeEach(async ({ page, request }) => {
      page.setViewportSize({ width: 1920, height: 1080 });
      page.on('console', message => {
        if (message.type() === 'error') {
          errors += 1;
        }
      });

      const content = galata.newContentsHelper(request);
      await content.deleteDirectory('/examples');
      await content.uploadDirectory(
        path.resolve(__dirname, '../../examples'),
        '/examples'
      );
    });

    test.afterEach(async ({ page }) => {
      errors = 0;
    });

    test(`Should be able to add object to scene`, async ({ page }) => {
      await page.goto();

      const fileName = 'example2.FCStd';
      const fullPath = `examples/${fileName}`;
      await page.notebook.openByPath(fullPath);
      await page.notebook.activate(fullPath);
      await page.locator('div.jpcad-Spinner').waitFor({ state: 'hidden' });

      await page.getByTitle('New Box').click();

      const nameInput = await page.locator(
        'input[id^="id-jp-schemaform"][label="Name"]'
      );
      await nameInput.fill('Foo');
      const accept = await page.locator('div.jp-Dialog-buttonLabel', {
        hasText: 'Submit'
      });
      await accept.click();

      await page
        .getByRole('tablist', { name: 'main sidebar' })
        .getByRole('tab', { name: 'JupyterCad Control Panel' })
        .click();
      await page
        .getByRole('tablist', { name: 'alternate sidebar' })
        .getByRole('tab', { name: 'JupyterCad Control Panel' })
        .click();

      await page.waitForTimeout(1000);
      expect(errors).toBe(0);
      const main = await page.$('#jp-main-split-panel');
      if (main) {
        expect(await main.screenshot()).toMatchSnapshot({
          name: `Operator-Add-${fileName}.png`,
          maxDiffPixelRatio: 0.01
        });
      }
    });

    test(`Should be able to remove object`, async ({ page }) => {
      await page.goto();

      const fileName = 'example3.FCStd';
      const fullPath = `examples/${fileName}`;
      await page.notebook.openByPath(fullPath);
      await page.notebook.activate(fullPath);
      await page.locator('div.jpcad-Spinner').waitFor({ state: 'hidden' });
      await page
        .locator('[data-test-id="react-tree-root"]')
        .getByText('Cut')
        .click();
      await page
        .locator('[data-test-id="react-tree-root"]')
        .getByRole('button')
        .nth(1)
        .click();

      if (await page.getByRole('button', { name: 'Ok' }).isVisible()) {
        await page.getByRole('button', { name: 'Ok' }).click();
      }

      await page
        .getByRole('tablist', { name: 'main sidebar' })
        .getByRole('tab', { name: 'JupyterCad Control Panel' })
        .click();
      await page
        .getByRole('tablist', { name: 'alternate sidebar' })
        .getByRole('tab', { name: 'JupyterCad Control Panel' })
        .click();

      await page.waitForTimeout(1000);
      expect(errors).toBe(0);
      const main = await page.$('#jp-main-split-panel');
      if (main) {
        expect(await main.screenshot()).toMatchSnapshot({
          name: `Operator-Remove-${fileName}.png`,
          maxDiffPixelRatio: 0.01
        });
      }
    });

    test(`Should be able to edit object`, async ({ page }) => {
      await page.goto();

      const fileName = 'example4.FCStd';
      const fullPath = `examples/${fileName}`;
      await page.notebook.openByPath(fullPath);
      await page.notebook.activate(fullPath);
      await page.locator('div.jpcad-Spinner').waitFor({ state: 'hidden' });

      await page
        .locator('[data-test-id="react-tree-root"]')
        .getByText('myBox')
        .click();
      await page
        .locator('[data-test-id="react-tree-root"]')
        .getByText('Shape')
        .click();
      await page.getByLabel('Height*').click();
      await page.getByLabel('Height*').fill('32');
      await page.getByRole('button', { name: 'Submit' }).click();

      // Deselect object for the screenshot
      await page
        .locator('[data-test-id="react-tree-root"]')
        .getByText('Shape')
        .click();

      // Hide side bars for the screenshot
      await page
        .getByRole('tablist', { name: 'main sidebar' })
        .getByRole('tab', { name: 'JupyterCad Control Panel' })
        .click();
      await page
        .getByRole('tablist', { name: 'alternate sidebar' })
        .getByRole('tab', { name: 'JupyterCad Control Panel' })
        .click();

      await page.waitForTimeout(1000);
      expect(errors).toBe(0);
      const main = await page.$('#jp-main-split-panel');
      if (main) {
        expect(await main.screenshot()).toMatchSnapshot({
          name: `Operator-Edit-${fileName}.png`,
          maxDiffPixelRatio: 0.01
        });
      }
    });

    test(`Should be able to do multi selection`, async ({ page }) => {
      await page.goto();

      const fileName = 'example3.FCStd';
      const fullPath = `examples/${fileName}`;
      await page.notebook.openByPath(fullPath);
      await page.notebook.activate(fullPath);
      await page.locator('div.jpcad-Spinner').waitFor({ state: 'hidden' });

      // Create a cone
      await page.getByTitle('New Cone').click();

      await page.getByLabel('Radius1').click();
      await page.getByLabel('Radius1').fill('15');
      await page.getByLabel('Radius2').click();
      await page.getByLabel('Radius2').fill('5');
      await page.getByLabel('Height').click();
      await page.getByLabel('Height').fill('20');
      await page
        .locator('div.jp-Dialog-buttonLabel', {
          hasText: 'Submit'
        })
        .click();

      // Select cone
      await page
        .locator('[data-test-id="react-tree-root"]')
        .getByText('Cone 1')
        .click();

      // Select other shape with ctrl key pressed
      await page.keyboard.down('Control');
      await page
        .locator('[data-test-id="react-tree-root"]')
        .getByText('Cut')
        .click();

      let main = await page.$('#jp-main-split-panel');
      if (main) {
        expect(await main.screenshot()).toMatchSnapshot({
          name: `MultiSelect-${fileName}.png`
        });
      }

      await page.waitForTimeout(1000);

      // Apply a cut operator from the selection
      await page.getByTitle('Cut', { exact: true }).click();
      await page
        .locator('.jp-Dialog-body')
        .locator('div.jp-Dialog-buttonLabel', {
          hasText: 'Submit'
        })
        .click();

      main = await page.$('#jp-main-split-panel');
      if (main) {
        expect(await main.screenshot()).toMatchSnapshot({
          name: `MultiSelect-Cut-${fileName}.png`
        });
      }
    });
  });
});
