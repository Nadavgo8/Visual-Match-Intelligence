import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {validFrame,interpolate} from '../../web/match-motion.mjs';
test('performance replay is pinned, complete and actively changes its source world',()=>{
  const bytes=readFileSync(new URL('../../web/diagnostics/performance-replay.json',import.meta.url));
  assert.equal(createHash('sha256').update(bytes).digest('hex'),'14d3f73aca88d78e8151fdb65d7c27ad42a916d38a77950a1848e668706ae446');
  const replay=JSON.parse(bytes);
  assert.equal(replay.seed,12);assert.equal(replay.generator_version,'2.3.0');
  assert.equal(replay.frames.length,601);assert.equal(replay.frames[0].t,600);assert.equal(replay.frames.at(-1).t,630);
  assert.ok(replay.frames.every(f=>validFrame(f)&&f.players.length===22));
  assert.ok(new Set(replay.frames.map(f=>f.ball.join(','))).size>100,'the diagnostic must not measure a frozen match image');
  const a=replay.frames[40],b=replay.frames[41],sample=interpolate(a,b,602.025);
  assert.equal(sample.t,602.025);assert.equal(sample.players.length,22);
  assert.ok(replay.meters.length>10,'the accessibility layer has actual delivered evidence');
});
