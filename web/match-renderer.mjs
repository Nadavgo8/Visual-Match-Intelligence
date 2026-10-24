import { pitchProjection, ballAppearance } from "./match-motion.mjs";

// Original procedural artwork. Canvas owns football drawing only; overlay is DOM.
export class MatchRenderer {
  constructor(canvas) {
    this.canvas = canvas; this.ctx = canvas.getContext("2d");
    this.background = canvas.ownerDocument.createElement("canvas");
    this.resize();
  }
  resize() {
    const ratio = Math.min(2, window.devicePixelRatio || 1);
    const width = Math.max(640, Math.round(this.canvas.clientWidth * ratio));
    const height = Math.round(width * 9 / 16);
    if (this.canvas.width === width && this.canvas.height === height && this.projection) return;
    this.canvas.width = this.background.width = width;
    this.canvas.height = this.background.height = height;
    // Draw in a stable design coordinate system, independent of device pixel ratio.
    this.ctx.setTransform(width / 1600, 0, 0, height / 900, 0, 0);
    this.projection = pitchProjection(1600, 900);
    const c = this.background.getContext("2d");
    c.setTransform(width / 1600, 0, 0, height / 900, 0, 0);
    const p = this.projection, xy = p.point;
    c.fillStyle = "#122e29"; c.fillRect(0, 0, 1600, 900);
    for (let i = 0; i < 14; i++) {
      c.fillStyle = i % 2 ? "#28674a" : "#246044";
      c.fillRect(p.left + i * 7.5 * p.scale, p.top, 7.5 * p.scale + 1, 68 * p.scale);
    }
    c.strokeStyle = "#d4e6ce"; c.lineWidth = 2; c.lineJoin = "round";
    const line = (x, y, xx, yy) => { c.beginPath(); c.moveTo(...xy(x, y)); c.lineTo(...xy(xx, yy)); c.stroke(); };
    const rect = (x, y, w, h) => { const [xx, yy] = xy(x, y + h); c.strokeRect(xx, yy, w * p.scale, h * p.scale); };
    rect(0, 0, 105, 68); line(52.5, 0, 52.5, 68);
    c.beginPath(); c.arc(...xy(52.5, 34), 9.15 * p.scale, 0, Math.PI * 2); c.stroke();
    for (const home of [true, false]) {
      const x = home ? 0 : 105, d = home ? 1 : -1;
      rect(home ? 0 : 88.5, 13.84, 16.5, 40.32);
      rect(home ? 0 : 99.5, 24.84, 5.5, 18.32);
      c.beginPath(); c.arc(...xy(x + d * 11, 34), 2.5, 0, Math.PI * 2); c.fillStyle = "#d4e6ce"; c.fill();
      const center = xy(x + d * 11, 34), angle = Math.acos(5.5 / 9.15);
      c.beginPath(); c.arc(...center, 9.15 * p.scale, home ? -angle : Math.PI - angle, home ? angle : Math.PI + angle); c.stroke();
      c.fillStyle = "#b3c6c642";
      const goal = xy(x + (home ? -2.3 : 0), 37.66);
      c.fillRect(goal[0], goal[1], 2.3 * p.scale, 7.32 * p.scale);
      rect(x + (home ? -2.3 : 0), 30.34, 2.3, 7.32);
    }
    c.beginPath(); c.arc(...xy(52.5, 34), 3, 0, Math.PI * 2); c.fill();
  }
  draw(frame, teams) {
    this.resize(); const c = this.ctx, p = this.projection;
    c.drawImage(this.background, 0, 0, 1600, 900);
    if (!frame || !teams) return;
    for (const player of frame.players) {
      const [x, y] = p.point(player.x, player.y), home = player.team === "home";
      c.fillStyle = "#0005"; c.beginPath(); c.ellipse(x + 3, y + 9, 13, 6, 0, 0, Math.PI * 2); c.fill();
      c.fillStyle = "#141f2a"; c.fillRect(x - 8, y + 3, 6, 9); c.fillRect(x + 2, y + 3, 6, 9);
      c.fillStyle = player.role === "GK" ? (home ? "#e9b359" : "#e38ebc") : teams[player.team].colour;
      c.strokeStyle = home ? "#edf8ff" : "#162a3b"; c.lineWidth = 1.8;
      c.beginPath(); c.roundRect(x - 11, y - 12, 22, 20, 5); c.fill(); c.stroke();
      // Away kit has a dark central stripe as an additional non-colour distinction.
      if (!home && player.role !== "GK") { c.fillStyle = "#183950"; c.fillRect(x - 2, y - 11, 4, 17); }
      c.fillStyle = "#ead1ad"; c.beginPath(); c.arc(x, y - 15, 4.8, 0, Math.PI * 2); c.fill();
      c.fillStyle = home || player.role === "GK" ? "#fff" : "#101f2b";
      c.font = "800 12px system-ui"; c.textAlign = "center"; c.textBaseline = "middle";
      c.strokeStyle = home ? "#142c56" : "#fff"; c.lineWidth = 2.5;
      c.strokeText(String(player.n), x, y - 1); c.fillText(String(player.n), x, y - 1);
    }
    const [x, y] = p.point(...frame.ball), b = ballAppearance(frame.ball_height, p.scale);
    c.fillStyle = `rgba(0,0,0,${b.shadowOpacity})`; c.beginPath(); c.ellipse(x + 2, y + 3, b.shadowRadius, b.shadowRadius * 0.55, 0, 0, Math.PI * 2); c.fill();
    c.fillStyle = "#fff"; c.strokeStyle = "#142d32"; c.lineWidth = 1.8;
    c.beginPath(); c.arc(x, y - b.lift, b.radius, 0, Math.PI * 2); c.fill(); c.stroke();
    c.fillStyle = "#163239"; c.fillRect(x - 1.5, y - b.lift - 1.5, 3, 3);
  }
}
