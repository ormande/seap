'use client';

import { signIn, useSession } from 'next-auth/react';
import { useEffect } from 'react';
import { useRouter } from 'next/navigation';

export default function LoginPage() {
  const { status } = useSession();
  const router = useRouter();

  useEffect(() => {
    if (status === 'authenticated') {
      router.replace('/');
    }
  }, [status, router]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-[#020617] bg-gradient-to-br from-slate-950 via-slate-900 to-emerald-950 px-4">
      <div className="w-full max-w-md rounded-2xl border border-emerald-500/20 bg-black/40 p-8 shadow-xl shadow-black/60 backdrop-blur-xl">
        <div className="mb-6 flex flex-col items-center gap-4">
          <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-emerald-500 text-white shadow-lg shadow-emerald-500/40">
            <span className="text-2xl font-semibold tracking-tight">S</span>
          </div>
          <div className="text-center">
            <h1 className="text-lg font-semibold tracking-tight text-slate-50">
              SEAP — Sistema de Extração e Análise de Processos
            </h1>
            <p className="mt-2 text-xs text-slate-300">
              Faça login para continuar e acessar suas análises de processos licitatórios.
            </p>
          </div>
        </div>

        <button
          type="button"
          onClick={() => signIn('google', { callbackUrl: '/' })}
          className="mt-2 flex w-full items-center justify-center gap-3 rounded-full border border-slate-200 bg-white px-4 py-2.5 text-sm font-medium text-slate-900 shadow-sm transition hover:border-emerald-400 hover:bg-slate-50 hover:shadow-md"
        >
          <span className="flex h-6 w-6 items-center justify-center rounded-full bg-white">
            <svg
              className="h-4 w-4"
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 533.5 544.3"
            >
              <path
                fill="#4285f4"
                d="M533.5 278.4c0-17.4-1.6-34.1-4.7-50.3H272v95.2h146.9c-6.4 34.5-25.7 63.7-54.8 83.3v68h88.7c52 47.9 80.7 118.5 80.7 196.1z"
              />
              <path
                fill="#34a853"
                d="M272 544.3c73.7 0 135.8-24.4 181.1-66.2l-88.7-68c-24.6 16.5-56.2 26-92.4 26-71 0-131.1-47.9-152.7-112.2H25.7v70.4C70.9 486.2 165 544.3 272 544.3z"
              />
              <path
                fill="#fbbc04"
                d="M119.3 323.9c-10.4-31.3-10.4-65.3 0-96.6V157H25.7c-42.6 84.8-42.6 184.9 0 269.7z"
              />
              <path
                fill="#ea4335"
                d="M272 107.7c39.9-.6 78.1 14.9 106.9 43.3l79.6-79.6C407.4-10.1 333.5-22.1 272 22.6 165 22.6 70.9 80.7 25.7 187l93.6 70.4C140.9 155.6 201 107.7 272 107.7z"
              />
            </svg>
          </span>
          <span>Entrar com Google</span>
        </button>

        <p className="mt-6 text-center text-[11px] text-slate-400">
          Seu acesso é autenticado via Google. Nenhuma senha é armazenada pelo SEAP.
        </p>
      </div>
    </div>
  );
}

