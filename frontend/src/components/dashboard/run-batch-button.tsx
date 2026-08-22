"use client";

import { motion } from "motion/react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Loader2, Play } from "lucide-react";
import { runBatch } from "@/lib/api";
import { cn } from "@/lib/utils";

export function RunBatchButton({ n = 20 }: { n?: number }) {
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: () => runBatch(n),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["metrics"] });
      queryClient.invalidateQueries({ queryKey: ["decisions"] });
    },
  });

  return (
    <motion.button
      whileHover={{ scale: 1.02 }}
      whileTap={{ scale: 0.97 }}
      onClick={() => mutation.mutate()}
      disabled={mutation.isPending}
      className={cn(
        "inline-flex items-center gap-2 rounded-lg bg-primary text-primary-foreground px-5 py-2.5 text-sm font-medium shadow-sm",
        "disabled:opacity-70 disabled:cursor-not-allowed transition-colors hover:bg-primary/90"
      )}
    >
      {mutation.isPending ? (
        <>
          <Loader2 className="size-4 animate-spin" />
          Running batch…
        </>
      ) : (
        <>
          <Play className="size-4" />
          Run recovery batch
        </>
      )}
    </motion.button>
  );
}
