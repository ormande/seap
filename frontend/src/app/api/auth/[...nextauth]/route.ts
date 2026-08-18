import NextAuth from "next-auth";
import GoogleProvider from "next-auth/providers/google";

const handler = NextAuth({
  providers: [
    GoogleProvider({
      clientId: process.env.GOOGLE_CLIENT_ID!,
      clientSecret: process.env.GOOGLE_CLIENT_SECRET!,
    }),
  ],
  callbacks: {
    async jwt({ token, account }) {
      // Propaga accessToken do Google para uso posterior (ex.: chamadas ao backend)
      if (account && account.access_token) {
        ((token as unknown) as Record<string, unknown>).accessToken = account.access_token;
      }
      return token;
    },
    async session({ session, token }) {
      // Adicionar user ID e accessToken à sessão
      if (session.user) {
        ((session.user as unknown) as Record<string, unknown>).id = token.sub;
      }
      ((session as unknown) as Record<string, unknown>).accessToken =
        ((token as unknown) as Record<string, unknown>).accessToken ?? null;
      return session;
    },
  },
  pages: {
    signIn: "/login",
  },
});

export { handler as GET, handler as POST };

