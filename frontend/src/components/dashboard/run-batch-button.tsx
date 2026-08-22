"use client";

import { motion } from "motion/react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Play } from "lucide-react";
import { runBatch } from "@/lib/api";
import { cn } from "@/lib/utils";
import { LoadingLine } from "@/components/motion/loading-line";

export function RunBatchButton({ n = 12 }: { n?: number }) {
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: () => runBatch(n),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["metrics"] });
      queryClient.invalidateQueries({ queryKey: ["decisions"] });
    },
  });

  return (
    <div className="flex flex-col items-end gap-1.5">
      <motion.button
        whileHover={{ scale: 1.02 }}
        whileTap={{ scale: 0.97 }}
        onClick={() => mutation.mutate()}
        disabled={mutation.isPending}
        className={cn(
          "inline-flex items-center gap-2 rounded-lg px-5 py-2.5 text-sm font-medium shadow-sm transition-colors",
          mutation.isPending
            ? "bg-processing/15 text-processing cursor-not-allowed"
            : "bg-primary text-primary-foreground hover:bg-primary/90"
        )}
      >
        {mutation.isPending ? (
          <>Diagnosing events…</>
        ) : (
          <>
            <Play className="size-4" />
            Run recovery batch
          </>
        )}
      </motion.button>
      {mutation.isPending && <LoadingLine className="w-40" />}
    </div>
  );
}
