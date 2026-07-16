import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { ChatMessage } from "@/types/chat";

import { MessageBubble } from "./MessageBubble";

function baseMessage(overrides: Partial<ChatMessage> = {}): ChatMessage {
  return {
    id: "1",
    role: "assistant",
    content: "Here's the answer.",
    createdAt: "2026-01-01T00:00:00.000Z",
    ...overrides,
  };
}

describe("MessageBubble", () => {
  it("renders the clarification indicator instead of a groundedness warning", () => {
    render(
      <MessageBubble
        message={baseMessage({ needsClarification: true, grounded: false })}
      />,
    );

    expect(screen.getByText("Clarifying question")).toBeInTheDocument();
    expect(screen.queryByText("This answer may be incomplete")).not.toBeInTheDocument();
  });

  it("shows an ungrounded warning when grounded is false and it isn't a clarification", () => {
    render(<MessageBubble message={baseMessage({ grounded: false })} />);

    expect(screen.getByText("This answer may be incomplete")).toBeInTheDocument();
  });

  it("shows no warning for a grounded answer", () => {
    render(<MessageBubble message={baseMessage({ grounded: true })} />);

    expect(screen.queryByText("This answer may be incomplete")).not.toBeInTheDocument();
    expect(screen.queryByText("Clarifying question")).not.toBeInTheDocument();
  });

  it("never shows indicators for the user's own message", () => {
    render(
      <MessageBubble
        message={baseMessage({ role: "user", grounded: false, needsClarification: true })}
      />,
    );

    expect(screen.queryByText("This answer may be incomplete")).not.toBeInTheDocument();
    expect(screen.queryByText("Clarifying question")).not.toBeInTheDocument();
  });

  it("renders a source count trigger when citations are present", () => {
    render(
      <MessageBubble
        message={baseMessage({
          citations: [
            { title: "Parking Permits", url: "https://example.edu/parking", department: "Parking", topic: "transportation" },
          ],
        })}
      />,
    );

    expect(screen.getByRole("button", { name: /1 source/i })).toBeInTheDocument();
  });

  it("shows feedback buttons for a normal assistant answer when a handler is provided", () => {
    render(<MessageBubble message={baseMessage()} onRateFeedback={vi.fn()} />);

    expect(screen.getByRole("button", { name: /was helpful/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /was not helpful/i })).toBeInTheDocument();
  });

  it("does not show feedback buttons without a handler", () => {
    render(<MessageBubble message={baseMessage()} />);

    expect(screen.queryByRole("button", { name: /helpful/i })).not.toBeInTheDocument();
  });

  it("does not show feedback buttons on a clarification message", () => {
    render(
      <MessageBubble
        message={baseMessage({ needsClarification: true })}
        onRateFeedback={vi.fn()}
      />,
    );

    expect(screen.queryByRole("button", { name: /helpful/i })).not.toBeInTheDocument();
  });

  it("never shows feedback buttons for the user's own message", () => {
    render(
      <MessageBubble message={baseMessage({ role: "user" })} onRateFeedback={vi.fn()} />,
    );

    expect(screen.queryByRole("button", { name: /helpful/i })).not.toBeInTheDocument();
  });

  it("calls onRateFeedback with the message id and chosen rating", async () => {
    const onRateFeedback = vi.fn();
    const user = userEvent.setup();
    render(<MessageBubble message={baseMessage({ id: "msg-42" })} onRateFeedback={onRateFeedback} />);

    await user.click(screen.getByRole("button", { name: /this answer was helpful/i }));

    expect(onRateFeedback).toHaveBeenCalledWith("msg-42", "helpful");
  });

  it("shows a thank-you message once feedback has been given", () => {
    render(
      <MessageBubble
        message={baseMessage({ feedback: "helpful" })}
        onRateFeedback={vi.fn()}
      />,
    );

    expect(screen.getByText(/thanks for the feedback/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /this answer was helpful/i })).not.toBeInTheDocument();
  });

  it("hides the debug topic line when debugMode is off, even with a topic set", () => {
    render(
      <MessageBubble
        message={baseMessage({ topic: "financial_aid", classificationConfidence: 0.82 })}
      />,
    );

    expect(screen.queryByText(/Topic:/)).not.toBeInTheDocument();
  });

  it("shows a formatted debug topic line when debugMode is on", () => {
    render(
      <MessageBubble
        message={baseMessage({ topic: "financial_aid", classificationConfidence: 0.82 })}
        debugMode
      />,
    );

    expect(screen.getByText("Topic: financial_aid (0.82)")).toBeInTheDocument();
  });

  it("hides the debug topic line when debugMode is on but the message has no topic", () => {
    render(<MessageBubble message={baseMessage()} debugMode />);

    expect(screen.queryByText(/Topic:/)).not.toBeInTheDocument();
  });
});
