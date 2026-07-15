import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

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
});
