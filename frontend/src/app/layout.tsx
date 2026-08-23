import type { Metadata } from "next";
import { Plus_Jakarta_Sans, Geist_Mono } from "next/font/google";
import { ThemeProvider } from "next-themes";
import "./globals.css";
import { Providers } from "./providers";
import { ChatWidget } from "@/components/chatbot/chat-widget";
import { ThemeToggle } from "@/components/motion/theme-toggle";

const sans = Plus_Jakarta_Sans({
  variable: "--font-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Vasuli — AI Revenue Recovery Agent",
  description:
    "Vasuli watches failed payments, abandoned checkouts, failed mandates, and overdue invoices, diagnoses why they're losing money, and recovers what it safely can — under hard guardrails, with a full audit trail.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`${sans.variable} ${geistMono.variable} h-full antialiased`}
      suppressHydrationWarning
    >
      <body className="min-h-full flex flex-col bg-background text-foreground">
        <ThemeProvider attribute="class" defaultTheme="light" enableSystem={false}>
          <Providers>{children}</Providers>
          <ChatWidget />
          <ThemeToggle
            variant="circle"
            start="bottom-up"
            className="fixed top-5 right-5 z-50 flex size-10 items-center justify-center rounded-full border border-border/60 bg-card shadow-lg hover:bg-accent transition-colors"
            iconClassName="size-4"
          />
        </ThemeProvider>
      </body>
    </html>
  );
}
