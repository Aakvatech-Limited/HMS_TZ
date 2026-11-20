import assert from "node:assert/strict";
import { describe, test } from "node:test";
import { createSSRApp, h } from "vue";
import { renderToString } from "vue/server-renderer";
import {
  injectDialogError,
  provideDialogError,
  providerReplyOf,
} from "../src/composables/dialogError.js";

const render = (component) => renderToString(createSSRApp(component));

describe("dialog error owner", () => {
  test("components inside a dialog report to that dialog's error", async () => {
    let owned;
    let injected;
    const Child = {
      setup: () => () => h("span", (injected = injectDialogError()) && ""),
    };
    await render({
      setup() {
        owned = provideDialogError();
        return () => h(Child);
      },
    });
    assert.equal(injected, owned);
    assert.equal(owned.value, null);
  });

  test("a nested dialog owns its own error", async () => {
    let outer;
    let inner;
    let injected;
    const Leaf = {
      setup: () => () => h("span", (injected = injectDialogError()) && ""),
    };
    const Nested = {
      setup() {
        inner = provideDialogError();
        return () => h(Leaf);
      },
    };
    await render({
      setup() {
        outer = provideDialogError();
        return () => h(Nested);
      },
    });
    assert.equal(injected, inner);
    assert.notEqual(injected, outer);
  });

  test("outside a dialog there is no owner, so errors stay toasts", async () => {
    let injected;
    await render({
      setup: () => () => h("span", (injected = injectDialogError()) && ""),
    });
    assert.equal(injected, null);
    assert.equal(injectDialogError(), null);
  });
});

describe("provider reply", () => {
  test("reads the title and message of a ProviderReplyError", () => {
    const reply = {
      title: "NHIF Error",
      message: "NHIF Response: Card is inactive",
    };
    assert.deepEqual(
      providerReplyOf({
        exc_type: "ProviderReplyError",
        messages: [JSON.stringify(reply)],
      }),
      reply
    );
  });

  test("other errors have no provider reply", () => {
    assert.equal(
      providerReplyOf({ exc_type: "ValidationError", messages: ["Overlap"] }),
      null
    );
    assert.equal(providerReplyOf(undefined), null);
  });
});
