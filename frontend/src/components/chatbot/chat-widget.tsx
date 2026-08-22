"use client";

import { useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { MessageCircle, X, ArrowUp, Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";
import { useAutoResizeTextarea } from "@/hooks/use-auto-resize-textarea";
import { LoadingLine } from "@/components/motion/loading-line";

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

const SUGGESTIONS = [
  "What does the guardrail engine block?",
  "How does the LLM fallback work?",
  "What happens when nothing can be recovered?",
];

async function sendChat(messages: ChatMessage[]): Promise<string> {
  const response = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ messages }),
  });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.error ?? "Chat request failed");
  }
  return data.reply as string;
}

export function ChatWidget() {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [value, setValue] = useState("");
  const [pending, setPending] = useState(false);
  const { textareaRef, adjustHeight } = useAutoResizeTextarea({ minHeight: 44, maxHeight: 140 });

  const submit = async (text: string) => {
    const trimmed = text.trim();
    if (!trimmed || pending) return;

    const nextMessages: ChatMessage[] = [...messages, { role: "user", content: trimmed }];
    setMessages(nextMessages);
    setValue("");
    adjustHeight(true);
    setPending(true);

    try {
      const reply = await sendChat(nextMessages);
      setMessages((prev) => [...prev, { role: "assistant", content: reply }]);
    } catch {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: "Sorry, I couldn't reach the assistant just now." },
      ]);
    } finally {
      setPending(false);
    }
  };

  return (
    <>
      <div className="fixed bottom-5 right-5 z-50">
        <AnimatePresence>
          {open && (
            <motion.div
              initial={{ opacity: 0, y: 16, scale: 0.96 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 16, scale: 0.96 }}
              transition={{ type: "spring", stiffness: 300, damping: 28 }}
              className="absolute bottom-16 right-0 w-[min(380px,calc(100vw-2.5rem))] rounded-2xl border border-border/60 bg-card shadow-2xl overflow-hidden flex flex-col"
              style={{ height: "min(560px, 70vh)" }}
            >
              <div className="flex items-center gap-2 border-b border-border/50 px-4 py-3">
                <Sparkles className="size-4 text-primary" />
                <div>
                  <p className="text-sm font-medium">Vasuli assistant</p>
                  <p className="text-xs text-muted-foreground">Ask how the recovery flow works</p>
                </div>
              </div>

              <div className="flex-1 overflow-y-auto px-4 py-3 space-y-3">
                {messages.length === 0 && (
                  <div className="space-y-2">
                    <p className="text-sm text-muted-foreground">
                      I know how Vasuli's guardrails, diagnosis agent, and audit trail work — ask
                      me anything about the flow.
                    </p>
                    {SUGGESTIONS.map((s) => (
                      <button
                        key={s}
                        onClick={() => submit(s)}
                        className="block w-full text-left text-xs rounded-lg border border-border/50 px-3 py-2 text-muted-foreground hover:bg-accent hover:text-accent-foreground transition-colors"
                      >
                        {s}
                      </button>
                    ))}
                  </div>
                )}
                {messages.map((m, i) => (
                  <motion.div
                    key={i}
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    className={cn(
                      "max-w-[85%] rounded-xl px-3 py-2 text-sm leading-relaxed",
                      m.role === "user"
                        ? "ml-auto bg-primary text-primary-foreground"
                        : "bg-muted text-foreground"
                    )}
                  >
                    {m.content}
                  </motion.div>
                ))}
                {pending && (
                  <div className="space-y-1.5 w-24">
                    <p className="text-xs text-muted-foreground">Thinking…</p>
                    <LoadingLine />
                  </div>
                )}
              </div>

              <div className="border-t border-border/50 p-2.5 flex items-end gap-2">
                <textarea
                  ref={textareaRef}
                  value={value}
                  onChange={(e) => {
                    setValue(e.target.value);
                    adjustHeight();
                  }}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault();
                      submit(value);
                    }
                  }}
                  placeholder="Ask about Vasuli…"
                  className="flex-1 resize-none rounded-lg bg-muted/60 px-3 py-2.5 text-sm outline-none placeholder:text-muted-foreground"
                  rows={1}
                />
                <button
                  onClick={() => submit(value)}
                  disabled={!value.trim() || pending}
                  className="shrink-0 rounded-lg bg-primary text-primary-foreground p-2.5 disabled:opacity-40 disabled:cursor-not-allowed hover:bg-primary/90 transition-colors"
                  aria-label="Send"
                >
                  <ArrowUp className="size-4" />
                </button>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        <motion.button
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.95 }}
          onClick={() => setOpen((o) => !o)}
          className="flex size-12 items-center justify-center rounded-full bg-primary text-primary-foreground shadow-lg hover:bg-primary/90 transition-colors"
          aria-label={open ? "Close assistant" : "Open assistant"}
        >
          <AnimatePresence mode="wait" initial={false}>
            <motion.span
              key={open ? "close" : "open"}
              initial={{ opacity: 0, rotate: -45 }}
              animate={{ opacity: 1, rotate: 0 }}
              exit={{ opacity: 0, rotate: 45 }}
              transition={{ duration: 0.15 }}
            >
              {open ? <X className="size-5" /> : <MessageCircle className="size-5" />}
            </motion.span>
          </AnimatePresence>
        </motion.button>
      </div>
    </>
  );
}
