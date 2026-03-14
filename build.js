/**
 * build.js — DualMomentumDashboard.jsx → dashboard.js 컴파일
 * GitHub Actions에서 실행: node build.js
 * 필요 패키지: @babel/standalone
 */

const fs = require('fs');

// @babel/standalone을 Node.js에서 사용
const babel = require('@babel/standalone');

const src = fs.readFileSync('DualMomentumDashboard.jsx', 'utf-8');

try {
  const result = babel.transform(src, {
    presets: ['react'],
    filename: 'DualMomentumDashboard.jsx',
  });

  // ReactDOM.createRoot 호출이 없으면 추가 (혹시 빠진 경우 대비)
  let code = result.code;

  fs.writeFileSync('dashboard.js', code, 'utf-8');
  console.log('✅ dashboard.js 컴파일 완료 (' + (code.length / 1024).toFixed(1) + ' KB)');
} catch (e) {
  console.error('❌ 컴파일 실패:', e.message);
  process.exit(1);
}
