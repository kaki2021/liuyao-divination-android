'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
let bytes=[0,0,0],calls=0;
const window={crypto:{getRandomValues(target){assert.equal(target.length,3);target.set(bytes);calls++;return target;}}};
vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../../liuyao_app/static/random-coin.js'),'utf8'),{window,Uint8Array});
const model=window.RandomCoinInput;
// Exhaust every equiprobable triple of coin bits: the four states must occur
// exactly 1:3:3:1. This checks mapping, not empirical prediction accuracy.
const histogram={old_yin:0,young_yang:0,young_yin:0,old_yang:0};
for(let bits=0;bits<8;bits++){
  bytes=[bits&1,(bits>>1)&1,(bits>>2)&1];
  const raw=model.drawThree();
  assert.equal(raw,bytes.map(bit=>bit?'3':'2').join(''));
  const state=model.derive([raw])[0];histogram[state]++;
  assert.equal(model.derive([raw]).slice(1).every(value=>value===null),true);
}
assert.deepEqual(histogram,{old_yin:1,young_yang:3,young_yin:3,old_yang:1});
// Every byte value contributes the same number of heads/tails possibilities.
let yin=0,yang=0;
for(let byte=0;byte<256;byte++){
  bytes=[byte,254,255];const raw=model.drawThree();
  if(raw[0]==='2')yin++;else if(raw[0]==='3')yang++;
  assert.equal(raw.slice(1),'23');
}
assert.deepEqual([yin,yang],[128,128]);
const before=calls;model.derive(['222','232','332','333','322','323']);assert.equal(calls,before);
window.crypto=undefined;
assert.throws(()=>model.drawThree(),/系统随机数/);
window.crypto={getRandomValues(){throw Error('entropy unavailable');}};
assert.throws(()=>model.drawThree(),/entropy unavailable/);
console.log('PASS: random-coin unbiased byte mapping, all eight coin triples, exact 1:3:3:1 states, no draws during derivation, no weak-random fallback.');
