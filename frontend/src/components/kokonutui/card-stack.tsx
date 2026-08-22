"use client";

/**
 * @author: @dorianbaffier (adapted for Vasuli)
 * @description: Card Stack — click to fan out
 * @license: MIT
 * @website: https://kokonutui.com
 * @github: https://github.com/kokonut-labs/kokonutui
 */

import { motion, useReducedMotion } from "motion/react";
import { useState, type ComponentType } from "react";
import { RefreshCw, Link2, MessageSquareText, Building2 } from "lucide-react";
import { cn } from "@/lib/utils";

interface Specification {
  label: string;
  value: string;
}

interface RecoveryAction {
  id: string;
  title: string;
  subtitle: string;
  description: string;
  icon: ComponentType<{ className?: string }>;
  specs: Specification[];
}

const actions: RecoveryAction[] = [
  {
    id: "smart-retry",
    title: "Smart",
    subtitle: "Retry",
    description:
      "Retries a failed payment at a model-recommended window — immediate for transient errors, next-day for insufficient funds.",
    icon: RefreshCw,
    specs: [
      { label: "Trigger", value: "Bank/network" },
      { label: "Timing", value: "Root-cause aware" },
      { label: "Cap", value: "1 / 30 min" },
      { label: "Route", value: "Razorpay" },
    ],
  },
  {
    id: "payment-link",
    title: "Payment",
    subtitle: "Link",
    description:
      "Generates a real Razorpay test-mode link when the same method won't work twice — card expired, hard declines.",
    icon: Link2,
    specs: [
      { label: "Mode", value: "Test, live API" },
      { label: "Best for", value: "Card expired" },
      { label: "Delivery", value: "Direct link" },
      { label: "Cost", value: "₹0" },
    ],
  },
  {
    id: "nudge",
    title: "Send",
    subtitle: "Nudge",
    description:
      "A Hinglish or English reminder on the customer's preferred channel — capped at 2 touches per day, respects opt-outs.",
    icon: MessageSquareText,
    specs: [
      { label: "Channel", value: "WhatsApp/SMS" },
      { label: "Language", value: "Hinglish/EN" },
      { label: "Cool-down", value: "4 hours" },
      { label: "Opt-out", value: "Enforced" },
    ],
  },
  {
    id: "b2b-chase",
    title: "B2B",
    subtitle: "Chase",
    description:
      "Tiered reminders for overdue invoices, firmer for unreliable payers. Anything over ₹1L is flagged for human review only.",
    icon: Building2,
    specs: [
      { label: "Tiering", value: "Reliability score" },
      { label: "Auto cap", value: "₹1,00,000" },
      { label: "Above cap", value: "Human review" },
      { label: "Tone", value: "Escalating" },
    ],
  },
];

const CARD_WIDTH = 300;
const CARD_OVERLAP = 150;

interface CardProps {
  action: RecoveryAction;
  index: number;
  totalCards: number;
  isExpanded: boolean;
  reducedMotion: boolean;
}

const Card = ({ action, index, totalCards, isExpanded, reducedMotion }: CardProps) => {
  const centerOffset = (totalCards - 1) * 5;
  const defaultX = index * 10 - centerOffset;
  const defaultY = index * 2;
  const defaultRotate = index * 1.5;

  const totalExpandedWidth = CARD_WIDTH + (totalCards - 1) * (CARD_WIDTH - CARD_OVERLAP);
  const expandedCenterOffset = totalExpandedWidth / 2;

  const spreadX = index * (CARD_WIDTH - CARD_OVERLAP) - expandedCenterOffset + CARD_WIDTH / 2;
  const spreadRotate = index * 5 - (totalCards - 1) * 2.5;

  const collapsedPose = {
    x: defaultX,
    y: defaultY,
    rotate: reducedMotion ? 0 : defaultRotate,
    scale: 1,
  };

  const expandedPose = {
    x: spreadX,
    y: 0,
    rotate: reducedMotion ? 0 : spreadRotate,
    scale: 1,
  };

  const Icon = action.icon;

  return (
    <motion.div
      animate={{
        ...(isExpanded ? expandedPose : collapsedPose),
        zIndex: totalCards - index,
      }}
      className={cn(
        "absolute inset-0 w-full rounded-2xl p-6",
        "bg-card/80 border border-border/60 backdrop-blur-xl backdrop-saturate-150",
        "shadow-[0_8px_20px_rgb(0,0,0,0.3)]",
        "hover:border-primary/30 hover:shadow-[0_12px_40px_rgb(0,0,0,0.4)]",
        "transition-[border-color,box-shadow] duration-300 ease-out",
        "transform-gpu overflow-hidden"
      )}
      initial={collapsedPose}
      style={{
        maxWidth: `${CARD_WIDTH}px`,
        left: "50%",
        marginLeft: `-${CARD_WIDTH / 2}px`,
      }}
      transition={
        reducedMotion
          ? { duration: 0.2, ease: "easeOut" }
          : {
              type: "spring",
              stiffness: 220,
              damping: 28,
              mass: 1,
              delay: isExpanded ? index * 0.04 : 0,
            }
      }
    >
      <div className="relative z-10">
        <dl className="mb-4 grid grid-cols-4 justify-center gap-2">
          {action.specs.map((spec) => (
            <div className="flex flex-col items-start text-left text-[10px]" key={spec.label}>
              <dd className="w-full text-left font-medium text-primary">{spec.value}</dd>
              <dt className="mb-0.5 w-full text-left text-muted-foreground">{spec.label}</dt>
            </div>
          ))}
        </dl>

        <div
          className={cn(
            "relative aspect-[16/11] w-full overflow-hidden rounded-lg",
            "bg-muted/40 border border-border/50 shadow-inner",
            "flex items-center justify-center"
          )}
        >
          <Icon className="size-12 text-primary/70" />
        </div>

        <div className="mt-4">
          <div className="space-y-1">
            <span className="block text-left font-bold text-3xl text-foreground tracking-tight">
              {action.title}
            </span>
            <span className="block text-left font-semibold text-3xl text-muted-foreground tracking-tight">
              {action.subtitle}
            </span>
          </div>
          <p className="mt-2 text-left text-muted-foreground text-sm">{action.description}</p>
        </div>
      </div>
    </motion.div>
  );
};

interface CardStackProps {
  className?: string;
}

export default function CardStackExample({ className }: CardStackProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const reducedMotion = useReducedMotion() ?? false;

  const handleToggle = () => setIsExpanded((prev) => !prev);

  return (
    <button
      aria-expanded={isExpanded}
      aria-label={isExpanded ? "Collapse recovery action cards" : "Expand recovery action cards"}
      className={cn(
        "relative mx-auto cursor-pointer",
        "min-h-[400px] w-full max-w-[90vw]",
        "md:max-w-[1100px]",
        "appearance-none border-0 bg-transparent p-0",
        "mb-8 flex items-center justify-center",
        className
      )}
      onClick={handleToggle}
      type="button"
    >
      {actions.map((action, index) => (
        <Card
          index={index}
          isExpanded={isExpanded}
          key={action.id}
          action={action}
          reducedMotion={reducedMotion}
          totalCards={actions.length}
        />
      ))}
    </button>
  );
}
