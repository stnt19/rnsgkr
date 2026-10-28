const {test} = require('node:test');
const assert = require('node:assert/strict');
const {LiveRecognitionLoop} = require('../web/live-core.js');

const flush = async () => { for(let i=0;i<8;i++) await Promise.resolve(); };
function deferred(){let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b;});return {promise,resolve,reject};}
function harness(overrides={}){
  const tasks=[];const results=[];const errors=[];
  const schedule=(fn,delay)=>{const task={fn,delay,cleared:false};tasks.push(task);return task;};
  const loop=new LiveRecognitionLoop({capture:()=> 'frame',infer:async()=>({candidates:[]}),
    onResult:r=>results.push(r),onError:e=>{errors.push(e);return true;},clock:()=>0,
    intervalMs:500,timeoutMs:10000,schedule,cancel:t=>t.cleared=true,...overrides});
  return {loop,results,errors,tasks,pending:()=>tasks.filter(t=>!t.cleared)};
}

test('only one frame is analyzed until its response completes',async()=>{
  const request=deferred();let calls=0;const h=harness({infer:()=>{calls++;return request.promise;}});
  h.loop.start();h.loop.start();await flush();assert.equal(calls,1);assert.equal(h.results.length,0);
  request.resolve({id:'battery'});await flush();assert.equal(h.results.length,1);
  const next=h.pending().find(t=>t.delay===500);assert.ok(next);next.cleared=true;next.fn();await flush();assert.equal(calls,2);h.loop.stop();
});
test('stopping aborts request and discards late results',async()=>{
  const request=deferred();let signal;const h=harness({infer:(_,s)=>{signal=s;return request.promise;}});
  h.loop.start();await flush();h.loop.stop();assert.ok(signal.aborted);
  request.resolve({id:'old'});await flush();assert.equal(h.results.length,0);assert.equal(h.pending().length,0);
});
test('restarting does not accept previous camera-session response',async()=>{
  const old=deferred(),fresh=deferred();let calls=0;const h=harness({infer:()=>++calls===1?old.promise:fresh.promise});
  h.loop.start();await flush();h.loop.stop();h.loop.start();await flush();
  fresh.resolve({id:'new'});await flush();old.resolve({id:'old'});await flush();assert.deepEqual(h.results,[{id:'new'}]);h.loop.stop();
});
test('temporary failure backs off instead of flooding server',async()=>{
  const h=harness({infer:async()=>{throw new Error('busy');}});h.loop.start();await flush();
  assert.equal(h.errors.length,1);assert.ok(h.pending().some(t=>t.delay>=2000));h.loop.stop();
});
test('fatal configuration error stops automatic inference',async()=>{
  const h=harness({infer:async()=>{throw new Error('no model');},onError:()=>false});h.loop.start();await flush();
  assert.equal(h.loop.running,false);assert.equal(h.pending().length,0);
});
test('a stopped capture cannot send a frame',async()=>{
  const capture=deferred();let calls=0;const h=harness({capture:()=>capture.promise,infer:async()=>{calls++;}});
  h.loop.start();h.loop.stop();capture.resolve('late-frame');await flush();assert.equal(calls,0);
});
test('request deadline aborts and reports a recoverable failure',async()=>{
  const h=harness({infer:(_,signal)=>new Promise((_,reject)=>signal.addEventListener('abort',()=>reject(new DOMException('Timeout','AbortError'))))});
  h.loop.start();await flush();const deadline=h.pending().find(t=>t.delay===10000);deadline.fn();await flush();
  assert.equal(h.errors[0].name,'AbortError');assert.ok(h.pending().some(t=>t.delay===2000));h.loop.stop();
});
test('inference longer than interval does not accumulate scheduled frames',async()=>{
  let time=0;const h=harness({clock:()=>time,infer:async()=>{time=1600;return {};}});h.loop.start();await flush();
  assert.equal(h.pending().length,1);assert.equal(h.pending()[0].delay,0);h.loop.stop();
});
