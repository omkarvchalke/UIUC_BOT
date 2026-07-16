"use client";

import { BarChart3, Bug, GraduationCap, RotateCcw } from "lucide-react";
import Link from "next/link";

import { ChatInput } from "@/components/chat/ChatInput";
import { ChatWindow } from "@/components/chat/ChatWindow";
import { StudentTypeSelector } from "@/components/chat/StudentTypeSelector";
import { SuggestedQuestions } from "@/components/chat/SuggestedQuestions";
import { ThemeToggle } from "@/components/ThemeToggle";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useChat } from "@/hooks/useChat";
import { useDebugMode } from "@/hooks/useDebugMode";
import { useSession } from "@/hooks/useSession";
import { cn } from "@/lib/utils";

export default function ChatPage() {
  const {
    sessionId,
    isReady,
    isStarting,
    error: sessionError,
    startSession,
    resetSession,
  } = useSession();
  const {
    messages,
    isSending,
    error: chatError,
    sendMessage,
    clearHistory,
    submitFeedback,
  } = useChat(sessionId);
  const { debugMode, toggleDebugMode } = useDebugMode();

  function handleNewConversation() {
    clearHistory();
    resetSession();
  }

  return (
    <div className="flex h-dvh flex-col">
      <div className="from-il-orange via-il-orange to-il-blue h-1 shrink-0 bg-gradient-to-r" />
      <header className="bg-background/95 border-foreground sticky top-0 z-10 flex items-center justify-between border-b-2 px-4 py-3 backdrop-blur">
        <div className="flex items-center gap-2.5">
          <span className="brutal-border bg-primary text-primary-foreground flex h-9 w-9 shrink-0 items-center justify-center rounded-xl">
            <GraduationCap className="h-5 w-5" strokeWidth={2.5} />
          </span>
          <span className="font-heading flex items-baseline gap-0.5 text-lg font-bold tracking-tight">
            Illini<span className="text-primary">Assist</span>
            <span className="text-muted-foreground ml-1 text-xs font-medium tracking-wide">
              AI
            </span>
          </span>
        </div>
        <div className="flex items-center gap-1">
          {sessionId && (
            <Button
              variant="ghost"
              size="icon"
              onClick={handleNewConversation}
              aria-label="Start a new conversation"
            >
              <RotateCcw className="h-4 w-4" />
            </Button>
          )}
          <Button
            variant="ghost"
            size="icon"
            onClick={toggleDebugMode}
            aria-label={debugMode ? "Turn off debug mode" : "Turn on debug mode"}
            aria-pressed={debugMode}
          >
            <Bug className={cn("h-4 w-4", debugMode && "text-primary")} />
          </Button>
          <Button
            variant="ghost"
            size="icon"
            aria-label="View analytics dashboard"
            render={<Link href="/analytics" />}
          >
            <BarChart3 className="h-4 w-4" />
          </Button>
          <ThemeToggle />
        </div>
      </header>

      <main className="flex flex-1 flex-col overflow-hidden">
        {!isReady ? (
          <div className="flex flex-1 items-center justify-center p-4">
            <div className="w-full max-w-lg space-y-3">
              <Skeleton className="mx-auto h-6 w-2/3" />
              <Skeleton className="h-24 w-full" />
            </div>
          </div>
        ) : !sessionId ? (
          <div className="flex flex-1 items-center justify-center py-10">
            <div className="flex flex-col items-center gap-3">
              <StudentTypeSelector onSelect={startSession} isLoading={isStarting} />
              {sessionError && <p className="text-destructive text-xs">{sessionError}</p>}
            </div>
          </div>
        ) : (
          <>
            <div className="min-h-0 flex-1">
              {messages.length === 0 ? (
                <div className="flex h-full flex-col items-center justify-center gap-6 px-4 text-center">
                  <div className="space-y-1.5">
                    <h2 className="font-heading text-xl font-bold tracking-tight uppercase">
                      What can I help you with?
                    </h2>
                    <p className="text-muted-foreground text-sm">
                      Try one of these, or ask your own question.
                    </p>
                  </div>
                  <SuggestedQuestions onSelect={sendMessage} disabled={isSending} />
                </div>
              ) : (
                <ChatWindow
                  messages={messages}
                  isSending={isSending}
                  onRateFeedback={submitFeedback}
                  debugMode={debugMode}
                />
              )}
            </div>
            <div className="border-t px-4 py-4">
              {chatError && (
                <p className="text-destructive mx-auto mb-2 max-w-2xl text-center text-xs">
                  {chatError}
                </p>
              )}
              <ChatInput onSend={sendMessage} disabled={isSending} />
            </div>
          </>
        )}
      </main>
    </div>
  );
}
