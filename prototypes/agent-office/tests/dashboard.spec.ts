import {test,expect} from '@playwright/test';
test('room and roster selection stay in sync',async({page})=>{
 await page.goto('/');
 await page.getByRole('button',{name:/Ada Builder/}).click();
 await expect(page.locator('.details h2')).toHaveText('Ada Builder');
 await expect(page.getByRole('button',{name:'Select Ada in office'})).toHaveAttribute('aria-pressed','true');
 await page.getByRole('button',{name:'Attention',exact:true}).click();
 await expect(page.locator('.details h2')).toHaveText('Cleo Reviewer');
 await page.getByRole('button',{name:'Select Milo in office'}).click();
 await expect(page.getByRole('button',{name:'All agents',exact:true})).toHaveAttribute('aria-pressed','true');
 await expect(page.locator('.details h2')).toHaveText('Milo Coordinator');
});
test('room updates with empty scenario',async({page})=>{
 await page.goto('/');await page.getByLabel('Demo scenario').selectOption('empty');
 await expect(page.locator('.scene-host')).toHaveAttribute('aria-label','Agent office: no agents');
 await expect(page.locator('.scene-label')).toHaveCount(0);
 await expect(page.getByRole('heading',{name:'A fresh start'})).toBeVisible();
});
test('WebGL unavailable preserves useful controls',async({page})=>{
 await page.addInitScript(()=>{const original=HTMLCanvasElement.prototype.getContext;HTMLCanvasElement.prototype.getContext=function(type:string,...args:unknown[]){if(type.includes('webgl'))return null;return original.apply(this,[type,...args] as never); } as typeof original;});
 await page.goto('/');await expect(page.getByText('The 3D view is unavailable')).toBeVisible();
 await page.getByRole('button',{name:/Noor Researcher/}).click();await expect(page.locator('.details h2')).toHaveText('Noor Researcher');
});
test('a character remains pickable after resizing',async({page})=>{
 await page.goto('/');
 for(const width of [1440,1000]){
  await page.setViewportSize({width,height:1000});
  await page.getByRole('button',{name:/Milo Coordinator/}).click();
  const label=page.getByRole('button',{name:'Select Ada in office'});
  await expect(label).toBeVisible();
  // The character is just above and right of its projected nameplate.
  const box=await label.boundingBox(); const canvas=await page.locator('canvas').boundingBox();
  const scale=canvas!.width/829;
  await page.mouse.click(box!.x+box!.width/2+12*scale,box!.y-25*scale);
  await expect(page.locator('.details h2')).toHaveText('Ada Builder');
 }
});
