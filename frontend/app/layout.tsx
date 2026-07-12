import type { Metadata } from "next";
import "./globals.css";
import PrompterNav from "../components/PrompterNav";

export const metadata: Metadata = {
  title: "ZoidLab Prompter",
  description: "Design, test, version, and deploy production prompts.",
  icons: { icon: "/logo.svg" },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="antialiased min-h-screen bg-bg text-ink">
        <PrompterNav />
        <main className="mx-auto w-full max-w-[1280px] px-5">{children}</main>
        <footer className="mx-auto mt-20 w-full max-w-[1280px] border-t border-line px-5 py-8 text-[12px] text-faint">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <span>ZoidLab Prompter · GitHub for enterprise AI prompts.</span>
            <span className="flex gap-4">
              <a href="https://foundry.zoidlab.ai" className="hover:text-dim">Foundry</a>
              <a href="https://zoidlab.ai" className="hover:text-dim">zoidlab.ai</a>
            </span>
          </div>
        </footer>
      </body>
    </html>
  );
}
