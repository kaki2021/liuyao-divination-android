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
console.log('Prepared',Object.keys(manifest.files).length,'scripts for',manifest.target);
