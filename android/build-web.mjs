// The source remains readable; the APK also supports the original Android 8 WebView syntax.
import {transformSync} from 'esbuild';
import {readFileSync,writeFileSync,readdirSync,mkdirSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {fileURLToPath} from 'node:url';
const source=new URL('../liuyao_app/static/',import.meta.url),output=new URL('./web/',import.meta.url);
mkdirSync(output,{recursive:true});
const manifest={target:'chrome58',tool:'esbuild 0.25.10',files:{}};
for(const name of readdirSync(source).filter(n=>n.endsWith('.js')).sort()){
 const input=readFileSync(new URL(name,source));
 const code=transformSync(input.toString(),{target:'chrome58',charset:'utf8',legalComments:'inline',sourcefile:name}).code;
 writeFileSync(new URL(name,output),code);
 manifest.files[name]={source:createHash('sha256').update(input).digest('hex'),output:createHash('sha256').update(code).digest('hex')};
}
writeFileSync(new URL('manifest.json',output),JSON.stringify(manifest,null,2)+'\n');
// Keep the exported illustrated guide completely offline and use the same
// navigation and styles as the in-app dialog. No third-party content is loaded.
const guidePath=new URL('user-guide.html',source);
const guide=readFileSync(guidePath,'utf8');
const guideCss=readFileSync(new URL('help.css',source),'utf8');
const guideJs=readFileSync(new URL('help-ui.js',output),'utf8');
writeFileSync(guidePath,guide
 .replace(/<style id="guide-styles">[\s\S]*?<\/style>/,'<style id="guide-styles">'+guideCss+'</style>')
 .replace(/<script id="guide-script">[\s\S]*?<\/script>/,'<script id="guide-script">'+guideJs+'</script>'));
console.log('Prepared',Object.keys(manifest.files).length,'scripts for',manifest.target);
