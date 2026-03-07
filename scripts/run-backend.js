/**
 * Roda o backend e reinicia automaticamente quando ele cair (ex.: erro no reload).
 * Ctrl+C encerra de vez (não reinicia).
 */
const path = require('path');
const { spawn } = require('child_process');

const isWindows = process.platform === 'win32';
const venvPython = isWindows
  ? 'C:\\Users\\User\\anaconda3\\envs\\projeto_pdf\\python.exe'
  : path.join(__dirname, '..', '.venv', 'bin', 'python');

function run() {
  const child = spawn(venvPython, ['-m', 'backend.main'], {
    stdio: 'inherit',
    shell: false,
    cwd: path.join(__dirname, '..'),
    env: { ...process.env, PYTHONIOENCODING: 'utf-8' },
  });

  child.on('exit', (code, signal) => {
    // 0 = sucesso, 130 = Ctrl+C (SIGINT), null = killed
    if (code === 0 || code === 130 || signal === 'SIGINT') {
      process.exit(code ?? 0);
      return;
    }
    console.error('[run-backend] Backend encerrou (código %s). Reiniciando em 2s...', code ?? signal);
    setTimeout(run, 2000);
  });
}

run();
