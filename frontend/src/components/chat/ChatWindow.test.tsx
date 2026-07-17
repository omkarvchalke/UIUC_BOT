import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { ChatMessage } from "@/types/chat";

import { ChatWindow } from "./ChatWindow";

function assistantMessage(overrides: Partial<ChatMessage> = {}): ChatMessage {
  return {
    id: "1",
    role: "assistant",
    content: "Here's the answer.",
    createdAt: "2026-01-01T00:00:00.000Z",
    ...overrides,
  };
}

describe("ChatWindow", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("does not show the slow-answer hint immediately", () => {
    render(<ChatWindow messages={[]} isSending />);

    expect(screen.queryByText(/still thinking/i)).not.toBeInTheDocument();
  });

  it("shows the slow-answer hint once the wait passes the threshold", () => {
    render(<ChatWindow messages={[]} isSending />);

    act(() => {
      vi.advanceTimersByTime(5000);
    });

    expect(screen.getByText(/still thinking/i)).toBeInTheDocument();
  });

  it("clears the slow-answer hint once sending finishes", () => {
    const { rerender } = render(<ChatWindow messages={[]} isSending />);
    act(() => {
      vi.advanceTimersByTime(5000);
    });
    expect(screen.getByText(/still thinking/i)).toBeInTheDocument();

    rerender(<ChatWindow messages={[]} isSending={false} />);

    expect(screen.queryByText(/still thinking/i)).not.toBeInTheDocument();
  });

  it("announces a plain-text excerpt of the latest answer once sending settles", () => {
    render(
      <ChatWindow
        messages={[assistantMessage({ content: "**Library hours** are [here](https://example.edu)." })]}
        isSending={false}
      />,
    );

    expect(screen.getByRole("status")).toHaveTextContent(
      "IlliniAssist: Library hours are here.",
    );
  });

  it("does not announce anything while still sending", () => {
    render(
      <ChatWindow messages={[assistantMessage()]} isSending />,
    );

    expect(screen.getByRole("status")).toHaveTextContent("");
  });
});
