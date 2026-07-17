import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ChatInput } from "./ChatInput";

describe("ChatInput", () => {
  it("submits the trimmed message and clears the input", async () => {
    const onSend = vi.fn();
    const user = userEvent.setup();
    render(<ChatInput onSend={onSend} />);

    const input = screen.getByLabelText("Message");
    await user.type(input, "  How do I apply for OPT?  ");
    await user.click(screen.getByRole("button", { name: /send message/i }));

    expect(onSend).toHaveBeenCalledWith("How do I apply for OPT?");
    expect(input).toHaveValue("");
  });

  it("does not submit an empty or whitespace-only message", async () => {
    const onSend = vi.fn();
    const user = userEvent.setup();
    render(<ChatInput onSend={onSend} />);

    await user.type(screen.getByLabelText("Message"), "   ");
    expect(screen.getByRole("button", { name: /send message/i })).toBeDisabled();

    await user.keyboard("{Enter}");
    expect(onSend).not.toHaveBeenCalled();
  });

  it("disables input and send button when disabled prop is true", () => {
    render(<ChatInput onSend={vi.fn()} disabled />);

    expect(screen.getByLabelText("Message")).toBeDisabled();
    expect(screen.getByRole("button", { name: /send message/i })).toBeDisabled();
  });

  it("restores the typed message if sending fails", async () => {
    const onSend = vi.fn().mockResolvedValue(false);
    const user = userEvent.setup();
    render(<ChatInput onSend={onSend} />);

    const input = screen.getByLabelText("Message");
    await user.type(input, "How do I apply for OPT?");
    await user.click(screen.getByRole("button", { name: /send message/i }));

    expect(onSend).toHaveBeenCalledWith("How do I apply for OPT?");
    expect(input).toHaveValue("How do I apply for OPT?");
  });

  it("focuses the input once it becomes enabled", () => {
    const { rerender } = render(<ChatInput onSend={vi.fn()} disabled />);
    expect(screen.getByLabelText("Message")).not.toHaveFocus();

    rerender(<ChatInput onSend={vi.fn()} />);
    expect(screen.getByLabelText("Message")).toHaveFocus();
  });

  it("does not auto-focus on a touch device", () => {
    const matchMediaSpy = vi
      .spyOn(window, "matchMedia")
      .mockImplementation((query: string) => ({
        matches: query === "(pointer: coarse)",
        media: query,
        onchange: null,
        addListener: () => {},
        removeListener: () => {},
        addEventListener: () => {},
        removeEventListener: () => {},
        dispatchEvent: () => false,
      }));

    const { rerender } = render(<ChatInput onSend={vi.fn()} disabled />);
    rerender(<ChatInput onSend={vi.fn()} />);

    expect(screen.getByLabelText("Message")).not.toHaveFocus();
    matchMediaSpy.mockRestore();
  });
});
