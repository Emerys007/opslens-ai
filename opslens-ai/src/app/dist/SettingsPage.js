(function(React2, react) {
  "use strict";
  const isRunningInWorker = () => typeof self !== "undefined" && self.__HUBSPOT_EXTENSION_WORKER__ === true;
  const fakeWorkerGlobals = {
    logger: {
      debug: (data) => {
        console.log(data);
      },
      info: (data) => {
        console.info(data);
      },
      warn: (data) => {
        console.warn(data);
      },
      error: (data) => {
        console.error(data);
      }
    },
    extend_V2: () => {
    },
    // @ts-expect-error we are not using the worker endpoint in tests env.
    __useExtensionContext: () => {
    }
  };
  const getWorkerGlobals = () => {
    return isRunningInWorker() ? self : fakeWorkerGlobals;
  };
  const extend_V2 = getWorkerGlobals().extend_V2;
  function serverless(name, options) {
    return self.serverless(name, options);
  }
  function fetch(url, options) {
    return self.hsFetch(url, options);
  }
  const hubspot = {
    extend: extend_V2,
    serverless,
    fetch
  };
  var ServerlessExecutionStatus;
  (function(ServerlessExecutionStatus2) {
    ServerlessExecutionStatus2["Success"] = "SUCCESS";
    ServerlessExecutionStatus2["Error"] = "ERROR";
  })(ServerlessExecutionStatus || (ServerlessExecutionStatus = {}));
  var jsxRuntime = { exports: {} };
  var reactJsxRuntime_development = {};
  var hasRequiredReactJsxRuntime_development;
  function requireReactJsxRuntime_development() {
    if (hasRequiredReactJsxRuntime_development) return reactJsxRuntime_development;
    hasRequiredReactJsxRuntime_development = 1;
    /**
     * @license React
     * react-jsx-runtime.development.js
     *
     * Copyright (c) Facebook, Inc. and its affiliates.
     *
     * This source code is licensed under the MIT license found in the
     * LICENSE file in the root directory of this source tree.
     */
    {
      (function() {
        var React$1 = React2;
        var REACT_ELEMENT_TYPE = Symbol.for("react.element");
        var REACT_PORTAL_TYPE = Symbol.for("react.portal");
        var REACT_FRAGMENT_TYPE = Symbol.for("react.fragment");
        var REACT_STRICT_MODE_TYPE = Symbol.for("react.strict_mode");
        var REACT_PROFILER_TYPE = Symbol.for("react.profiler");
        var REACT_PROVIDER_TYPE = Symbol.for("react.provider");
        var REACT_CONTEXT_TYPE = Symbol.for("react.context");
        var REACT_FORWARD_REF_TYPE = Symbol.for("react.forward_ref");
        var REACT_SUSPENSE_TYPE = Symbol.for("react.suspense");
        var REACT_SUSPENSE_LIST_TYPE = Symbol.for("react.suspense_list");
        var REACT_MEMO_TYPE = Symbol.for("react.memo");
        var REACT_LAZY_TYPE = Symbol.for("react.lazy");
        var REACT_OFFSCREEN_TYPE = Symbol.for("react.offscreen");
        var MAYBE_ITERATOR_SYMBOL = Symbol.iterator;
        var FAUX_ITERATOR_SYMBOL = "@@iterator";
        function getIteratorFn(maybeIterable) {
          if (maybeIterable === null || typeof maybeIterable !== "object") {
            return null;
          }
          var maybeIterator = MAYBE_ITERATOR_SYMBOL && maybeIterable[MAYBE_ITERATOR_SYMBOL] || maybeIterable[FAUX_ITERATOR_SYMBOL];
          if (typeof maybeIterator === "function") {
            return maybeIterator;
          }
          return null;
        }
        var ReactSharedInternals = React$1.__SECRET_INTERNALS_DO_NOT_USE_OR_YOU_WILL_BE_FIRED;
        function error(format) {
          {
            {
              for (var _len2 = arguments.length, args = new Array(_len2 > 1 ? _len2 - 1 : 0), _key2 = 1; _key2 < _len2; _key2++) {
                args[_key2 - 1] = arguments[_key2];
              }
              printWarning("error", format, args);
            }
          }
        }
        function printWarning(level, format, args) {
          {
            var ReactDebugCurrentFrame2 = ReactSharedInternals.ReactDebugCurrentFrame;
            var stack = ReactDebugCurrentFrame2.getStackAddendum();
            if (stack !== "") {
              format += "%s";
              args = args.concat([stack]);
            }
            var argsWithFormat = args.map(function(item) {
              return String(item);
            });
            argsWithFormat.unshift("Warning: " + format);
            Function.prototype.apply.call(console[level], console, argsWithFormat);
          }
        }
        var enableScopeAPI = false;
        var enableCacheElement = false;
        var enableTransitionTracing = false;
        var enableLegacyHidden = false;
        var enableDebugTracing = false;
        var REACT_MODULE_REFERENCE;
        {
          REACT_MODULE_REFERENCE = Symbol.for("react.module.reference");
        }
        function isValidElementType(type) {
          if (typeof type === "string" || typeof type === "function") {
            return true;
          }
          if (type === REACT_FRAGMENT_TYPE || type === REACT_PROFILER_TYPE || enableDebugTracing || type === REACT_STRICT_MODE_TYPE || type === REACT_SUSPENSE_TYPE || type === REACT_SUSPENSE_LIST_TYPE || enableLegacyHidden || type === REACT_OFFSCREEN_TYPE || enableScopeAPI || enableCacheElement || enableTransitionTracing) {
            return true;
          }
          if (typeof type === "object" && type !== null) {
            if (type.$$typeof === REACT_LAZY_TYPE || type.$$typeof === REACT_MEMO_TYPE || type.$$typeof === REACT_PROVIDER_TYPE || type.$$typeof === REACT_CONTEXT_TYPE || type.$$typeof === REACT_FORWARD_REF_TYPE || // This needs to include all possible module reference object
            // types supported by any Flight configuration anywhere since
            // we don't know which Flight build this will end up being used
            // with.
            type.$$typeof === REACT_MODULE_REFERENCE || type.getModuleId !== void 0) {
              return true;
            }
          }
          return false;
        }
        function getWrappedName(outerType, innerType, wrapperName) {
          var displayName = outerType.displayName;
          if (displayName) {
            return displayName;
          }
          var functionName = innerType.displayName || innerType.name || "";
          return functionName !== "" ? wrapperName + "(" + functionName + ")" : wrapperName;
        }
        function getContextName(type) {
          return type.displayName || "Context";
        }
        function getComponentNameFromType(type) {
          if (type == null) {
            return null;
          }
          {
            if (typeof type.tag === "number") {
              error("Received an unexpected object in getComponentNameFromType(). This is likely a bug in React. Please file an issue.");
            }
          }
          if (typeof type === "function") {
            return type.displayName || type.name || null;
          }
          if (typeof type === "string") {
            return type;
          }
          switch (type) {
            case REACT_FRAGMENT_TYPE:
              return "Fragment";
            case REACT_PORTAL_TYPE:
              return "Portal";
            case REACT_PROFILER_TYPE:
              return "Profiler";
            case REACT_STRICT_MODE_TYPE:
              return "StrictMode";
            case REACT_SUSPENSE_TYPE:
              return "Suspense";
            case REACT_SUSPENSE_LIST_TYPE:
              return "SuspenseList";
          }
          if (typeof type === "object") {
            switch (type.$$typeof) {
              case REACT_CONTEXT_TYPE:
                var context = type;
                return getContextName(context) + ".Consumer";
              case REACT_PROVIDER_TYPE:
                var provider = type;
                return getContextName(provider._context) + ".Provider";
              case REACT_FORWARD_REF_TYPE:
                return getWrappedName(type, type.render, "ForwardRef");
              case REACT_MEMO_TYPE:
                var outerName = type.displayName || null;
                if (outerName !== null) {
                  return outerName;
                }
                return getComponentNameFromType(type.type) || "Memo";
              case REACT_LAZY_TYPE: {
                var lazyComponent = type;
                var payload = lazyComponent._payload;
                var init = lazyComponent._init;
                try {
                  return getComponentNameFromType(init(payload));
                } catch (x) {
                  return null;
                }
              }
            }
          }
          return null;
        }
        var assign = Object.assign;
        var disabledDepth = 0;
        var prevLog;
        var prevInfo;
        var prevWarn;
        var prevError;
        var prevGroup;
        var prevGroupCollapsed;
        var prevGroupEnd;
        function disabledLog() {
        }
        disabledLog.__reactDisabledLog = true;
        function disableLogs() {
          {
            if (disabledDepth === 0) {
              prevLog = console.log;
              prevInfo = console.info;
              prevWarn = console.warn;
              prevError = console.error;
              prevGroup = console.group;
              prevGroupCollapsed = console.groupCollapsed;
              prevGroupEnd = console.groupEnd;
              var props = {
                configurable: true,
                enumerable: true,
                value: disabledLog,
                writable: true
              };
              Object.defineProperties(console, {
                info: props,
                log: props,
                warn: props,
                error: props,
                group: props,
                groupCollapsed: props,
                groupEnd: props
              });
            }
            disabledDepth++;
          }
        }
        function reenableLogs() {
          {
            disabledDepth--;
            if (disabledDepth === 0) {
              var props = {
                configurable: true,
                enumerable: true,
                writable: true
              };
              Object.defineProperties(console, {
                log: assign({}, props, {
                  value: prevLog
                }),
                info: assign({}, props, {
                  value: prevInfo
                }),
                warn: assign({}, props, {
                  value: prevWarn
                }),
                error: assign({}, props, {
                  value: prevError
                }),
                group: assign({}, props, {
                  value: prevGroup
                }),
                groupCollapsed: assign({}, props, {
                  value: prevGroupCollapsed
                }),
                groupEnd: assign({}, props, {
                  value: prevGroupEnd
                })
              });
            }
            if (disabledDepth < 0) {
              error("disabledDepth fell below zero. This is a bug in React. Please file an issue.");
            }
          }
        }
        var ReactCurrentDispatcher = ReactSharedInternals.ReactCurrentDispatcher;
        var prefix;
        function describeBuiltInComponentFrame(name, source, ownerFn) {
          {
            if (prefix === void 0) {
              try {
                throw Error();
              } catch (x) {
                var match = x.stack.trim().match(/\n( *(at )?)/);
                prefix = match && match[1] || "";
              }
            }
            return "\n" + prefix + name;
          }
        }
        var reentry = false;
        var componentFrameCache;
        {
          var PossiblyWeakMap = typeof WeakMap === "function" ? WeakMap : Map;
          componentFrameCache = new PossiblyWeakMap();
        }
        function describeNativeComponentFrame(fn, construct) {
          if (!fn || reentry) {
            return "";
          }
          {
            var frame = componentFrameCache.get(fn);
            if (frame !== void 0) {
              return frame;
            }
          }
          var control;
          reentry = true;
          var previousPrepareStackTrace = Error.prepareStackTrace;
          Error.prepareStackTrace = void 0;
          var previousDispatcher;
          {
            previousDispatcher = ReactCurrentDispatcher.current;
            ReactCurrentDispatcher.current = null;
            disableLogs();
          }
          try {
            if (construct) {
              var Fake = function() {
                throw Error();
              };
              Object.defineProperty(Fake.prototype, "props", {
                set: function() {
                  throw Error();
                }
              });
              if (typeof Reflect === "object" && Reflect.construct) {
                try {
                  Reflect.construct(Fake, []);
                } catch (x) {
                  control = x;
                }
                Reflect.construct(fn, [], Fake);
              } else {
                try {
                  Fake.call();
                } catch (x) {
                  control = x;
                }
                fn.call(Fake.prototype);
              }
            } else {
              try {
                throw Error();
              } catch (x) {
                control = x;
              }
              fn();
            }
          } catch (sample) {
            if (sample && control && typeof sample.stack === "string") {
              var sampleLines = sample.stack.split("\n");
              var controlLines = control.stack.split("\n");
              var s = sampleLines.length - 1;
              var c = controlLines.length - 1;
              while (s >= 1 && c >= 0 && sampleLines[s] !== controlLines[c]) {
                c--;
              }
              for (; s >= 1 && c >= 0; s--, c--) {
                if (sampleLines[s] !== controlLines[c]) {
                  if (s !== 1 || c !== 1) {
                    do {
                      s--;
                      c--;
                      if (c < 0 || sampleLines[s] !== controlLines[c]) {
                        var _frame = "\n" + sampleLines[s].replace(" at new ", " at ");
                        if (fn.displayName && _frame.includes("<anonymous>")) {
                          _frame = _frame.replace("<anonymous>", fn.displayName);
                        }
                        {
                          if (typeof fn === "function") {
                            componentFrameCache.set(fn, _frame);
                          }
                        }
                        return _frame;
                      }
                    } while (s >= 1 && c >= 0);
                  }
                  break;
                }
              }
            }
          } finally {
            reentry = false;
            {
              ReactCurrentDispatcher.current = previousDispatcher;
              reenableLogs();
            }
            Error.prepareStackTrace = previousPrepareStackTrace;
          }
          var name = fn ? fn.displayName || fn.name : "";
          var syntheticFrame = name ? describeBuiltInComponentFrame(name) : "";
          {
            if (typeof fn === "function") {
              componentFrameCache.set(fn, syntheticFrame);
            }
          }
          return syntheticFrame;
        }
        function describeFunctionComponentFrame(fn, source, ownerFn) {
          {
            return describeNativeComponentFrame(fn, false);
          }
        }
        function shouldConstruct(Component) {
          var prototype = Component.prototype;
          return !!(prototype && prototype.isReactComponent);
        }
        function describeUnknownElementTypeFrameInDEV(type, source, ownerFn) {
          if (type == null) {
            return "";
          }
          if (typeof type === "function") {
            {
              return describeNativeComponentFrame(type, shouldConstruct(type));
            }
          }
          if (typeof type === "string") {
            return describeBuiltInComponentFrame(type);
          }
          switch (type) {
            case REACT_SUSPENSE_TYPE:
              return describeBuiltInComponentFrame("Suspense");
            case REACT_SUSPENSE_LIST_TYPE:
              return describeBuiltInComponentFrame("SuspenseList");
          }
          if (typeof type === "object") {
            switch (type.$$typeof) {
              case REACT_FORWARD_REF_TYPE:
                return describeFunctionComponentFrame(type.render);
              case REACT_MEMO_TYPE:
                return describeUnknownElementTypeFrameInDEV(type.type, source, ownerFn);
              case REACT_LAZY_TYPE: {
                var lazyComponent = type;
                var payload = lazyComponent._payload;
                var init = lazyComponent._init;
                try {
                  return describeUnknownElementTypeFrameInDEV(init(payload), source, ownerFn);
                } catch (x) {
                }
              }
            }
          }
          return "";
        }
        var hasOwnProperty = Object.prototype.hasOwnProperty;
        var loggedTypeFailures = {};
        var ReactDebugCurrentFrame = ReactSharedInternals.ReactDebugCurrentFrame;
        function setCurrentlyValidatingElement(element) {
          {
            if (element) {
              var owner = element._owner;
              var stack = describeUnknownElementTypeFrameInDEV(element.type, element._source, owner ? owner.type : null);
              ReactDebugCurrentFrame.setExtraStackFrame(stack);
            } else {
              ReactDebugCurrentFrame.setExtraStackFrame(null);
            }
          }
        }
        function checkPropTypes(typeSpecs, values, location, componentName, element) {
          {
            var has = Function.call.bind(hasOwnProperty);
            for (var typeSpecName in typeSpecs) {
              if (has(typeSpecs, typeSpecName)) {
                var error$1 = void 0;
                try {
                  if (typeof typeSpecs[typeSpecName] !== "function") {
                    var err = Error((componentName || "React class") + ": " + location + " type `" + typeSpecName + "` is invalid; it must be a function, usually from the `prop-types` package, but received `" + typeof typeSpecs[typeSpecName] + "`.This often happens because of typos such as `PropTypes.function` instead of `PropTypes.func`.");
                    err.name = "Invariant Violation";
                    throw err;
                  }
                  error$1 = typeSpecs[typeSpecName](values, typeSpecName, componentName, location, null, "SECRET_DO_NOT_PASS_THIS_OR_YOU_WILL_BE_FIRED");
                } catch (ex) {
                  error$1 = ex;
                }
                if (error$1 && !(error$1 instanceof Error)) {
                  setCurrentlyValidatingElement(element);
                  error("%s: type specification of %s `%s` is invalid; the type checker function must return `null` or an `Error` but returned a %s. You may have forgotten to pass an argument to the type checker creator (arrayOf, instanceOf, objectOf, oneOf, oneOfType, and shape all require an argument).", componentName || "React class", location, typeSpecName, typeof error$1);
                  setCurrentlyValidatingElement(null);
                }
                if (error$1 instanceof Error && !(error$1.message in loggedTypeFailures)) {
                  loggedTypeFailures[error$1.message] = true;
                  setCurrentlyValidatingElement(element);
                  error("Failed %s type: %s", location, error$1.message);
                  setCurrentlyValidatingElement(null);
                }
              }
            }
          }
        }
        var isArrayImpl = Array.isArray;
        function isArray(a) {
          return isArrayImpl(a);
        }
        function typeName(value) {
          {
            var hasToStringTag = typeof Symbol === "function" && Symbol.toStringTag;
            var type = hasToStringTag && value[Symbol.toStringTag] || value.constructor.name || "Object";
            return type;
          }
        }
        function willCoercionThrow(value) {
          {
            try {
              testStringCoercion(value);
              return false;
            } catch (e) {
              return true;
            }
          }
        }
        function testStringCoercion(value) {
          return "" + value;
        }
        function checkKeyStringCoercion(value) {
          {
            if (willCoercionThrow(value)) {
              error("The provided key is an unsupported type %s. This value must be coerced to a string before before using it here.", typeName(value));
              return testStringCoercion(value);
            }
          }
        }
        var ReactCurrentOwner = ReactSharedInternals.ReactCurrentOwner;
        var RESERVED_PROPS = {
          key: true,
          ref: true,
          __self: true,
          __source: true
        };
        var specialPropKeyWarningShown;
        var specialPropRefWarningShown;
        function hasValidRef(config) {
          {
            if (hasOwnProperty.call(config, "ref")) {
              var getter = Object.getOwnPropertyDescriptor(config, "ref").get;
              if (getter && getter.isReactWarning) {
                return false;
              }
            }
          }
          return config.ref !== void 0;
        }
        function hasValidKey(config) {
          {
            if (hasOwnProperty.call(config, "key")) {
              var getter = Object.getOwnPropertyDescriptor(config, "key").get;
              if (getter && getter.isReactWarning) {
                return false;
              }
            }
          }
          return config.key !== void 0;
        }
        function warnIfStringRefCannotBeAutoConverted(config, self2) {
          {
            if (typeof config.ref === "string" && ReactCurrentOwner.current && self2) ;
          }
        }
        function defineKeyPropWarningGetter(props, displayName) {
          {
            var warnAboutAccessingKey = function() {
              if (!specialPropKeyWarningShown) {
                specialPropKeyWarningShown = true;
                error("%s: `key` is not a prop. Trying to access it will result in `undefined` being returned. If you need to access the same value within the child component, you should pass it as a different prop. (https://reactjs.org/link/special-props)", displayName);
              }
            };
            warnAboutAccessingKey.isReactWarning = true;
            Object.defineProperty(props, "key", {
              get: warnAboutAccessingKey,
              configurable: true
            });
          }
        }
        function defineRefPropWarningGetter(props, displayName) {
          {
            var warnAboutAccessingRef = function() {
              if (!specialPropRefWarningShown) {
                specialPropRefWarningShown = true;
                error("%s: `ref` is not a prop. Trying to access it will result in `undefined` being returned. If you need to access the same value within the child component, you should pass it as a different prop. (https://reactjs.org/link/special-props)", displayName);
              }
            };
            warnAboutAccessingRef.isReactWarning = true;
            Object.defineProperty(props, "ref", {
              get: warnAboutAccessingRef,
              configurable: true
            });
          }
        }
        var ReactElement = function(type, key, ref, self2, source, owner, props) {
          var element = {
            // This tag allows us to uniquely identify this as a React Element
            $$typeof: REACT_ELEMENT_TYPE,
            // Built-in properties that belong on the element
            type,
            key,
            ref,
            props,
            // Record the component responsible for creating this element.
            _owner: owner
          };
          {
            element._store = {};
            Object.defineProperty(element._store, "validated", {
              configurable: false,
              enumerable: false,
              writable: true,
              value: false
            });
            Object.defineProperty(element, "_self", {
              configurable: false,
              enumerable: false,
              writable: false,
              value: self2
            });
            Object.defineProperty(element, "_source", {
              configurable: false,
              enumerable: false,
              writable: false,
              value: source
            });
            if (Object.freeze) {
              Object.freeze(element.props);
              Object.freeze(element);
            }
          }
          return element;
        };
        function jsxDEV(type, config, maybeKey, source, self2) {
          {
            var propName;
            var props = {};
            var key = null;
            var ref = null;
            if (maybeKey !== void 0) {
              {
                checkKeyStringCoercion(maybeKey);
              }
              key = "" + maybeKey;
            }
            if (hasValidKey(config)) {
              {
                checkKeyStringCoercion(config.key);
              }
              key = "" + config.key;
            }
            if (hasValidRef(config)) {
              ref = config.ref;
              warnIfStringRefCannotBeAutoConverted(config, self2);
            }
            for (propName in config) {
              if (hasOwnProperty.call(config, propName) && !RESERVED_PROPS.hasOwnProperty(propName)) {
                props[propName] = config[propName];
              }
            }
            if (type && type.defaultProps) {
              var defaultProps = type.defaultProps;
              for (propName in defaultProps) {
                if (props[propName] === void 0) {
                  props[propName] = defaultProps[propName];
                }
              }
            }
            if (key || ref) {
              var displayName = typeof type === "function" ? type.displayName || type.name || "Unknown" : type;
              if (key) {
                defineKeyPropWarningGetter(props, displayName);
              }
              if (ref) {
                defineRefPropWarningGetter(props, displayName);
              }
            }
            return ReactElement(type, key, ref, self2, source, ReactCurrentOwner.current, props);
          }
        }
        var ReactCurrentOwner$1 = ReactSharedInternals.ReactCurrentOwner;
        var ReactDebugCurrentFrame$1 = ReactSharedInternals.ReactDebugCurrentFrame;
        function setCurrentlyValidatingElement$1(element) {
          {
            if (element) {
              var owner = element._owner;
              var stack = describeUnknownElementTypeFrameInDEV(element.type, element._source, owner ? owner.type : null);
              ReactDebugCurrentFrame$1.setExtraStackFrame(stack);
            } else {
              ReactDebugCurrentFrame$1.setExtraStackFrame(null);
            }
          }
        }
        var propTypesMisspellWarningShown;
        {
          propTypesMisspellWarningShown = false;
        }
        function isValidElement(object) {
          {
            return typeof object === "object" && object !== null && object.$$typeof === REACT_ELEMENT_TYPE;
          }
        }
        function getDeclarationErrorAddendum() {
          {
            if (ReactCurrentOwner$1.current) {
              var name = getComponentNameFromType(ReactCurrentOwner$1.current.type);
              if (name) {
                return "\n\nCheck the render method of `" + name + "`.";
              }
            }
            return "";
          }
        }
        function getSourceInfoErrorAddendum(source) {
          {
            return "";
          }
        }
        var ownerHasKeyUseWarning = {};
        function getCurrentComponentErrorInfo(parentType) {
          {
            var info = getDeclarationErrorAddendum();
            if (!info) {
              var parentName = typeof parentType === "string" ? parentType : parentType.displayName || parentType.name;
              if (parentName) {
                info = "\n\nCheck the top-level render call using <" + parentName + ">.";
              }
            }
            return info;
          }
        }
        function validateExplicitKey(element, parentType) {
          {
            if (!element._store || element._store.validated || element.key != null) {
              return;
            }
            element._store.validated = true;
            var currentComponentErrorInfo = getCurrentComponentErrorInfo(parentType);
            if (ownerHasKeyUseWarning[currentComponentErrorInfo]) {
              return;
            }
            ownerHasKeyUseWarning[currentComponentErrorInfo] = true;
            var childOwner = "";
            if (element && element._owner && element._owner !== ReactCurrentOwner$1.current) {
              childOwner = " It was passed a child from " + getComponentNameFromType(element._owner.type) + ".";
            }
            setCurrentlyValidatingElement$1(element);
            error('Each child in a list should have a unique "key" prop.%s%s See https://reactjs.org/link/warning-keys for more information.', currentComponentErrorInfo, childOwner);
            setCurrentlyValidatingElement$1(null);
          }
        }
        function validateChildKeys(node, parentType) {
          {
            if (typeof node !== "object") {
              return;
            }
            if (isArray(node)) {
              for (var i = 0; i < node.length; i++) {
                var child = node[i];
                if (isValidElement(child)) {
                  validateExplicitKey(child, parentType);
                }
              }
            } else if (isValidElement(node)) {
              if (node._store) {
                node._store.validated = true;
              }
            } else if (node) {
              var iteratorFn = getIteratorFn(node);
              if (typeof iteratorFn === "function") {
                if (iteratorFn !== node.entries) {
                  var iterator = iteratorFn.call(node);
                  var step;
                  while (!(step = iterator.next()).done) {
                    if (isValidElement(step.value)) {
                      validateExplicitKey(step.value, parentType);
                    }
                  }
                }
              }
            }
          }
        }
        function validatePropTypes(element) {
          {
            var type = element.type;
            if (type === null || type === void 0 || typeof type === "string") {
              return;
            }
            var propTypes;
            if (typeof type === "function") {
              propTypes = type.propTypes;
            } else if (typeof type === "object" && (type.$$typeof === REACT_FORWARD_REF_TYPE || // Note: Memo only checks outer props here.
            // Inner props are checked in the reconciler.
            type.$$typeof === REACT_MEMO_TYPE)) {
              propTypes = type.propTypes;
            } else {
              return;
            }
            if (propTypes) {
              var name = getComponentNameFromType(type);
              checkPropTypes(propTypes, element.props, "prop", name, element);
            } else if (type.PropTypes !== void 0 && !propTypesMisspellWarningShown) {
              propTypesMisspellWarningShown = true;
              var _name = getComponentNameFromType(type);
              error("Component %s declared `PropTypes` instead of `propTypes`. Did you misspell the property assignment?", _name || "Unknown");
            }
            if (typeof type.getDefaultProps === "function" && !type.getDefaultProps.isReactClassApproved) {
              error("getDefaultProps is only used on classic React.createClass definitions. Use a static property named `defaultProps` instead.");
            }
          }
        }
        function validateFragmentProps(fragment) {
          {
            var keys = Object.keys(fragment.props);
            for (var i = 0; i < keys.length; i++) {
              var key = keys[i];
              if (key !== "children" && key !== "key") {
                setCurrentlyValidatingElement$1(fragment);
                error("Invalid prop `%s` supplied to `React.Fragment`. React.Fragment can only have `key` and `children` props.", key);
                setCurrentlyValidatingElement$1(null);
                break;
              }
            }
            if (fragment.ref !== null) {
              setCurrentlyValidatingElement$1(fragment);
              error("Invalid attribute `ref` supplied to `React.Fragment`.");
              setCurrentlyValidatingElement$1(null);
            }
          }
        }
        var didWarnAboutKeySpread = {};
        function jsxWithValidation(type, props, key, isStaticChildren, source, self2) {
          {
            var validType = isValidElementType(type);
            if (!validType) {
              var info = "";
              if (type === void 0 || typeof type === "object" && type !== null && Object.keys(type).length === 0) {
                info += " You likely forgot to export your component from the file it's defined in, or you might have mixed up default and named imports.";
              }
              var sourceInfo = getSourceInfoErrorAddendum();
              if (sourceInfo) {
                info += sourceInfo;
              } else {
                info += getDeclarationErrorAddendum();
              }
              var typeString;
              if (type === null) {
                typeString = "null";
              } else if (isArray(type)) {
                typeString = "array";
              } else if (type !== void 0 && type.$$typeof === REACT_ELEMENT_TYPE) {
                typeString = "<" + (getComponentNameFromType(type.type) || "Unknown") + " />";
                info = " Did you accidentally export a JSX literal instead of a component?";
              } else {
                typeString = typeof type;
              }
              error("React.jsx: type is invalid -- expected a string (for built-in components) or a class/function (for composite components) but got: %s.%s", typeString, info);
            }
            var element = jsxDEV(type, props, key, source, self2);
            if (element == null) {
              return element;
            }
            if (validType) {
              var children = props.children;
              if (children !== void 0) {
                if (isStaticChildren) {
                  if (isArray(children)) {
                    for (var i = 0; i < children.length; i++) {
                      validateChildKeys(children[i], type);
                    }
                    if (Object.freeze) {
                      Object.freeze(children);
                    }
                  } else {
                    error("React.jsx: Static children should always be an array. You are likely explicitly calling React.jsxs or React.jsxDEV. Use the Babel transform instead.");
                  }
                } else {
                  validateChildKeys(children, type);
                }
              }
            }
            {
              if (hasOwnProperty.call(props, "key")) {
                var componentName = getComponentNameFromType(type);
                var keys = Object.keys(props).filter(function(k) {
                  return k !== "key";
                });
                var beforeExample = keys.length > 0 ? "{key: someKey, " + keys.join(": ..., ") + ": ...}" : "{key: someKey}";
                if (!didWarnAboutKeySpread[componentName + beforeExample]) {
                  var afterExample = keys.length > 0 ? "{" + keys.join(": ..., ") + ": ...}" : "{}";
                  error('A props object containing a "key" prop is being spread into JSX:\n  let props = %s;\n  <%s {...props} />\nReact keys must be passed directly to JSX without using spread:\n  let props = %s;\n  <%s key={someKey} {...props} />', beforeExample, componentName, afterExample, componentName);
                  didWarnAboutKeySpread[componentName + beforeExample] = true;
                }
              }
            }
            if (type === REACT_FRAGMENT_TYPE) {
              validateFragmentProps(element);
            } else {
              validatePropTypes(element);
            }
            return element;
          }
        }
        function jsxWithValidationStatic(type, props, key) {
          {
            return jsxWithValidation(type, props, key, true);
          }
        }
        function jsxWithValidationDynamic(type, props, key) {
          {
            return jsxWithValidation(type, props, key, false);
          }
        }
        var jsx = jsxWithValidationDynamic;
        var jsxs = jsxWithValidationStatic;
        reactJsxRuntime_development.Fragment = REACT_FRAGMENT_TYPE;
        reactJsxRuntime_development.jsx = jsx;
        reactJsxRuntime_development.jsxs = jsxs;
      })();
    }
    return reactJsxRuntime_development;
  }
  var hasRequiredJsxRuntime;
  function requireJsxRuntime() {
    if (hasRequiredJsxRuntime) return jsxRuntime.exports;
    hasRequiredJsxRuntime = 1;
    {
      jsxRuntime.exports = requireReactJsxRuntime_development();
    }
    return jsxRuntime.exports;
  }
  var jsxRuntimeExports = requireJsxRuntime();
  const createRemoteComponentRegistry = () => {
    const componentMetadataLookup = /* @__PURE__ */ new Map();
    const componentNameByComponentMap = /* @__PURE__ */ new Map();
    const registerComponent = (component, componentName, fragmentProps) => {
      componentNameByComponentMap.set(component, componentName);
      componentMetadataLookup.set(componentName, {
        fragmentPropsSet: new Set(fragmentProps),
        fragmentPropsArray: fragmentProps
      });
      return component;
    };
    return {
      getComponentName: (component) => {
        const componentName = componentNameByComponentMap.get(component);
        if (!componentName) {
          return null;
        }
        return componentName;
      },
      isAllowedComponentName: (componentName) => {
        return componentMetadataLookup.has(componentName);
      },
      isComponentFragmentProp: (componentName, propName) => {
        const componentMetadata = componentMetadataLookup.get(componentName);
        if (!componentMetadata) {
          return false;
        }
        return componentMetadata.fragmentPropsSet.has(propName);
      },
      getComponentFragmentPropNames: (componentName) => {
        const componentMetadata = componentMetadataLookup.get(componentName);
        if (!componentMetadata) {
          return [];
        }
        const { fragmentPropsArray } = componentMetadata;
        return fragmentPropsArray;
      },
      createAndRegisterRemoteReactComponent: (componentName, options = {}) => {
        const { fragmentProps = [] } = options;
        const remoteReactComponent = react.createRemoteReactComponent(componentName, {
          fragmentProps
        });
        return registerComponent(remoteReactComponent, componentName, fragmentProps);
      },
      createAndRegisterRemoteCompoundReactComponent: (componentName, options) => {
        const { fragmentProps = [] } = options;
        const RemoteComponentType = react.createRemoteReactComponent(componentName, {
          fragmentProps
        });
        const CompoundFunctionComponentType = typeof RemoteComponentType === "function" ? RemoteComponentType : (props) => jsxRuntimeExports.jsx(RemoteComponentType, { ...props });
        Object.assign(CompoundFunctionComponentType, options.compoundComponentProperties);
        return registerComponent(CompoundFunctionComponentType, componentName, fragmentProps);
      }
    };
  };
  const __hubSpotComponentRegistry = createRemoteComponentRegistry();
  const { createAndRegisterRemoteReactComponent, createAndRegisterRemoteCompoundReactComponent } = __hubSpotComponentRegistry;
  createAndRegisterRemoteReactComponent("Alert");
  const Button = createAndRegisterRemoteReactComponent("Button", {
    fragmentProps: ["overlay"]
  });
  createAndRegisterRemoteReactComponent("ButtonRow");
  createAndRegisterRemoteReactComponent("Card");
  createAndRegisterRemoteReactComponent("DescriptionList");
  createAndRegisterRemoteReactComponent("DescriptionListItem");
  const Divider = createAndRegisterRemoteReactComponent("Divider");
  createAndRegisterRemoteReactComponent("Spacer");
  const EmptyState = createAndRegisterRemoteReactComponent("EmptyState");
  createAndRegisterRemoteReactComponent("ErrorState");
  const Form = createAndRegisterRemoteReactComponent("Form");
  createAndRegisterRemoteReactComponent("Heading");
  createAndRegisterRemoteReactComponent("Image", {
    fragmentProps: ["overlay"]
  });
  const Input = createAndRegisterRemoteReactComponent("Input");
  createAndRegisterRemoteReactComponent("Link", {
    fragmentProps: ["overlay"]
  });
  const TextArea = createAndRegisterRemoteReactComponent("TextArea");
  createAndRegisterRemoteReactComponent("Textarea");
  createAndRegisterRemoteReactComponent("LoadingSpinner");
  createAndRegisterRemoteReactComponent("ProgressBar");
  const Select = createAndRegisterRemoteReactComponent("Select");
  createAndRegisterRemoteReactComponent("Tag", {
    fragmentProps: ["overlay"]
  });
  const Text = createAndRegisterRemoteReactComponent("Text");
  createAndRegisterRemoteReactComponent("Tile");
  createAndRegisterRemoteReactComponent("Stack");
  createAndRegisterRemoteReactComponent("ToggleGroup");
  createAndRegisterRemoteReactComponent("StatisticsItem");
  createAndRegisterRemoteReactComponent("Statistics");
  createAndRegisterRemoteReactComponent("StatisticsTrend");
  createAndRegisterRemoteReactComponent("Table");
  createAndRegisterRemoteReactComponent("TableFooter");
  createAndRegisterRemoteReactComponent("TableCell");
  createAndRegisterRemoteReactComponent("TableRow");
  createAndRegisterRemoteReactComponent("TableBody");
  createAndRegisterRemoteReactComponent("TableHeader");
  createAndRegisterRemoteReactComponent("TableHead");
  createAndRegisterRemoteReactComponent("NumberInput");
  const Box = createAndRegisterRemoteReactComponent("Box");
  createAndRegisterRemoteReactComponent("StepIndicator");
  createAndRegisterRemoteReactComponent("Accordion");
  createAndRegisterRemoteReactComponent("MultiSelect");
  const Flex = createAndRegisterRemoteReactComponent("Flex");
  createAndRegisterRemoteReactComponent("DateInput");
  createAndRegisterRemoteReactComponent("Checkbox");
  createAndRegisterRemoteReactComponent("RadioButton");
  createAndRegisterRemoteReactComponent("List");
  createAndRegisterRemoteReactComponent("Toggle");
  createAndRegisterRemoteCompoundReactComponent("Dropdown", {
    compoundComponentProperties: {
      /**
       * The `Dropdown.ButtonItem` component represents a single option within a `Dropdown` menu. Use this component as a child of the `Dropdown` component.
       *
       * **Links:**
       *
       * - {@link https://developers.hubspot.com/docs/reference/ui-components/standard-components/dropdown Docs}
       */
      ButtonItem: createAndRegisterRemoteReactComponent("DropdownButtonItem", {
        fragmentProps: ["overlay"]
      })
    }
  });
  createAndRegisterRemoteReactComponent("Panel");
  createAndRegisterRemoteReactComponent("PanelFooter");
  createAndRegisterRemoteReactComponent("PanelBody");
  createAndRegisterRemoteReactComponent("PanelSection");
  createAndRegisterRemoteReactComponent("StepperInput");
  createAndRegisterRemoteReactComponent("Modal");
  createAndRegisterRemoteReactComponent("ModalBody");
  createAndRegisterRemoteReactComponent("ModalFooter");
  createAndRegisterRemoteReactComponent("Icon");
  createAndRegisterRemoteReactComponent("StatusTag");
  createAndRegisterRemoteReactComponent("LoadingButton", {
    fragmentProps: ["overlay"]
  });
  createAndRegisterRemoteReactComponent("BarChart");
  createAndRegisterRemoteReactComponent("LineChart");
  createAndRegisterRemoteReactComponent("ScoreCircle");
  createAndRegisterRemoteReactComponent("Tabs");
  createAndRegisterRemoteReactComponent("Tab");
  createAndRegisterRemoteReactComponent("Illustration");
  createAndRegisterRemoteReactComponent("Tooltip");
  createAndRegisterRemoteReactComponent("SearchInput");
  createAndRegisterRemoteReactComponent("TimeInput");
  createAndRegisterRemoteReactComponent("CurrencyInput");
  createAndRegisterRemoteReactComponent("Inline");
  createAndRegisterRemoteReactComponent("AutoGrid");
  createAndRegisterRemoteReactComponent("CrmPropertyList");
  createAndRegisterRemoteReactComponent("CrmAssociationTable");
  createAndRegisterRemoteReactComponent("CrmDataHighlight");
  createAndRegisterRemoteReactComponent("CrmReport");
  createAndRegisterRemoteReactComponent("CrmAssociationPivot");
  createAndRegisterRemoteReactComponent("CrmAssociationPropertyList");
  createAndRegisterRemoteReactComponent("CrmAssociationStageTracker");
  createAndRegisterRemoteReactComponent("CrmSimpleDeadline");
  createAndRegisterRemoteReactComponent("CrmStageTracker");
  createAndRegisterRemoteReactComponent("CrmStatistics");
  createAndRegisterRemoteReactComponent("CrmActionButton");
  createAndRegisterRemoteReactComponent("CrmActionLink");
  createAndRegisterRemoteReactComponent("CrmCardActions");
  createAndRegisterRemoteReactComponent("HeaderActions");
  createAndRegisterRemoteReactComponent("PrimaryHeaderActionButton", {
    fragmentProps: ["overlay"]
  });
  createAndRegisterRemoteReactComponent("SecondaryHeaderActionButton", {
    fragmentProps: ["overlay"]
  });
  createAndRegisterRemoteReactComponent("PageLink");
  createAndRegisterRemoteReactComponent("Iframe");
  createAndRegisterRemoteReactComponent("MediaObject", {
    fragmentProps: ["itemRight", "itemLeft"]
  });
  createAndRegisterRemoteReactComponent("Stack2");
  createAndRegisterRemoteReactComponent("Center");
  createAndRegisterRemoteReactComponent("Grid");
  createAndRegisterRemoteReactComponent("GridItem");
  createAndRegisterRemoteReactComponent("SettingsView");
  createAndRegisterRemoteReactComponent("ExpandableText");
  createAndRegisterRemoteReactComponent("Popover");
  createAndRegisterRemoteReactComponent("FileInput");
  const MocksContext = React2.createContext(null);
  MocksContext.Provider;
  const BACKEND_BASE_URL = "https://opslens.local";
  hubspot.extend(({ context }) => {
    return /* @__PURE__ */ React2.createElement(SettingsPage, { context });
  });
  const SettingsPage = ({ context }) => {
    var _a, _b;
    const [loading, setLoading] = React2.useState(true);
    const [saveMessage, setSaveMessage] = React2.useState("");
    const [errorMessage, setErrorMessage] = React2.useState("");
    const [slackWebhookUrl, setSlackWebhookUrl] = React2.useState("");
    const [alertThreshold, setAlertThreshold] = React2.useState("high");
    const [criticalWorkflows, setCriticalWorkflows] = React2.useState("");
    const loadSettings = async () => {
      var _a2, _b2, _c;
      setLoading(true);
      setErrorMessage("");
      setSaveMessage("");
      try {
        const response = await hubspot.fetch(
          `${BACKEND_BASE_URL}/api/v1/settings-store`,
          {
            method: "GET",
            timeout: 3e3
          }
        );
        if (!response.ok) {
          throw new Error(`Backend returned status ${response.status}`);
        }
        const data = await response.json();
        setSlackWebhookUrl(((_a2 = data == null ? void 0 : data.settings) == null ? void 0 : _a2.slackWebhookUrl) ?? "");
        setAlertThreshold(((_b2 = data == null ? void 0 : data.settings) == null ? void 0 : _b2.alertThreshold) ?? "high");
        setCriticalWorkflows(((_c = data == null ? void 0 : data.settings) == null ? void 0 : _c.criticalWorkflows) ?? "");
      } catch (err) {
        console.error("Failed to load settings", err);
        setErrorMessage(err instanceof Error ? err.message : "Unknown error");
      } finally {
        setLoading(false);
      }
    };
    const saveSettings = async () => {
      setErrorMessage("");
      setSaveMessage("");
      try {
        const response = await hubspot.fetch(
          `${BACKEND_BASE_URL}/api/v1/settings-store`,
          {
            method: "POST",
            timeout: 3e3,
            body: {
              slackWebhookUrl,
              alertThreshold,
              criticalWorkflows
            }
          }
        );
        if (!response.ok) {
          throw new Error(`Backend returned status ${response.status}`);
        }
        const data = await response.json();
        setSaveMessage(`Saved at ${data.savedAtUtc}`);
      } catch (err) {
        console.error("Failed to save settings", err);
        setErrorMessage(err instanceof Error ? err.message : "Unknown error");
      }
    };
    React2.useEffect(() => {
      loadSettings().catch(
        (err) => console.error("Unexpected settings load error", err)
      );
    }, []);
    return /* @__PURE__ */ React2.createElement(Flex, { direction: "column", gap: "medium" }, /* @__PURE__ */ React2.createElement(EmptyState, { title: "OpsLens AI settings", layout: "vertical" }, /* @__PURE__ */ React2.createElement(Text, null, "This page now loads and saves portal-level OpsLens settings through the local Python backend.")), /* @__PURE__ */ React2.createElement(Divider, null), /* @__PURE__ */ React2.createElement(Box, null, /* @__PURE__ */ React2.createElement(Text, { format: { fontWeight: "bold" } }, "Backend status"), /* @__PURE__ */ React2.createElement(Text, null, loading ? "Loading settings..." : "Ready"), /* @__PURE__ */ React2.createElement(Text, null, errorMessage ? `Error: ${errorMessage}` : "No settings fetch error detected."), /* @__PURE__ */ React2.createElement(Text, null, saveMessage ? saveMessage : "No settings save event yet.")), /* @__PURE__ */ React2.createElement(Divider, null), /* @__PURE__ */ React2.createElement(
      Form,
      {
        preventDefault: true,
        onSubmit: () => {
          saveSettings().catch(
            (err) => console.error("Unexpected settings save error", err)
          );
        }
      },
      /* @__PURE__ */ React2.createElement(Flex, { direction: "column", gap: "medium" }, /* @__PURE__ */ React2.createElement(
        Input,
        {
          label: "Slack webhook URL",
          name: "slackWebhookUrl",
          value: slackWebhookUrl,
          onChange: (value) => setSlackWebhookUrl(value),
          placeholder: "https://hooks.slack.com/services/..."
        }
      ), /* @__PURE__ */ React2.createElement(
        Select,
        {
          label: "Alert threshold",
          name: "alertThreshold",
          value: alertThreshold,
          onChange: (value) => setAlertThreshold(String(value)),
          options: [
            { label: "Critical", value: "critical" },
            { label: "High", value: "high" },
            { label: "Medium", value: "medium" }
          ]
        }
      ), /* @__PURE__ */ React2.createElement(
        TextArea,
        {
          label: "Critical workflows",
          name: "criticalWorkflows",
          value: criticalWorkflows,
          onChange: (value) => setCriticalWorkflows(value),
          placeholder: "Quote Sync\nOwner Routing\nImport Cleanup",
          description: "One workflow name per line."
        }
      ), /* @__PURE__ */ React2.createElement(Button, { type: "submit" }, "Save settings"))
    ), /* @__PURE__ */ React2.createElement(Divider, null), /* @__PURE__ */ React2.createElement(Box, null, /* @__PURE__ */ React2.createElement(Text, { format: { fontWeight: "bold" } }, "Debug context"), /* @__PURE__ */ React2.createElement(Text, null, "Portal ID: ", String(((_a = context == null ? void 0 : context.portal) == null ? void 0 : _a.id) ?? "unknown")), /* @__PURE__ */ React2.createElement(Text, null, "User ID: ", String(((_b = context == null ? void 0 : context.user) == null ? void 0 : _b.id) ?? "unknown"))));
  };
})(React, RemoteUI);
//# sourceMappingURL=data:application/json;charset=utf-8;base64,eyJ2ZXJzaW9uIjozLCJmaWxlIjoiU2V0dGluZ3NQYWdlLmpzIiwic291cmNlcyI6WyIuLi9zZXR0aW5ncy9ub2RlX21vZHVsZXMvQGh1YnNwb3QvdWktZXh0ZW5zaW9ucy9kaXN0L2ludGVybmFsL2dsb2JhbC11dGlscy5qcyIsIi4uL3NldHRpbmdzL25vZGVfbW9kdWxlcy9AaHVic3BvdC91aS1leHRlbnNpb25zL2Rpc3QvaHVic3BvdC5qcyIsIi4uL3NldHRpbmdzL25vZGVfbW9kdWxlcy9AaHVic3BvdC91aS1leHRlbnNpb25zL2Rpc3Qvc2hhcmVkL3R5cGVzL2h0dHAtcmVxdWVzdHMuanMiLCIuLi9zZXR0aW5ncy9ub2RlX21vZHVsZXMvcmVhY3QvY2pzL3JlYWN0LWpzeC1ydW50aW1lLmRldmVsb3BtZW50LmpzIiwiLi4vc2V0dGluZ3Mvbm9kZV9tb2R1bGVzL3JlYWN0L2pzeC1ydW50aW1lLmpzIiwiLi4vc2V0dGluZ3Mvbm9kZV9tb2R1bGVzL0BodWJzcG90L3VpLWV4dGVuc2lvbnMvZGlzdC9zaGFyZWQvdXRpbHMvcmVtb3RlLWNvbXBvbmVudC1yZWdpc3RyeS5qcyIsIi4uL3NldHRpbmdzL25vZGVfbW9kdWxlcy9AaHVic3BvdC91aS1leHRlbnNpb25zL2Rpc3Qvc2hhcmVkL3JlbW90ZUNvbXBvbmVudHMuanMiLCIuLi9zZXR0aW5ncy9ub2RlX21vZHVsZXMvQGh1YnNwb3QvdWktZXh0ZW5zaW9ucy9kaXN0L2ludGVybmFsL2hvb2stdXRpbHMuanMiLCIuLi9zZXR0aW5ncy9TZXR0aW5nc1BhZ2UudHN4Il0sInNvdXJjZXNDb250ZW50IjpbIi8qKlxuICogQ2hlY2tzIGlmIHRoZSBjdXJyZW50IGVudmlyb25tZW50IGlzIGEgSHViU3BvdCBleHRlbnNpb24gd29ya2VyLlxuICogQHJldHVybnMgVHJ1ZSBpZiB0aGUgY3VycmVudCBlbnZpcm9ubWVudCBpcyBhIEh1YlNwb3QgZXh0ZW5zaW9uIHdvcmtlci5cbiAqL1xuY29uc3QgaXNSdW5uaW5nSW5Xb3JrZXIgPSAoKSA9PiB0eXBlb2Ygc2VsZiAhPT0gJ3VuZGVmaW5lZCcgJiZcbiAgICBzZWxmLl9fSFVCU1BPVF9FWFRFTlNJT05fV09SS0VSX18gPT09IHRydWU7XG4vKipcbiAqIEEgZmFrZSB3b3JrZXIgZ2xvYmFscyBvYmplY3QgZm9yIHVzZSBpbiB0ZXN0IGVudmlyb25tZW50cy5cbiAqL1xuY29uc3QgZmFrZVdvcmtlckdsb2JhbHMgPSB7XG4gICAgbG9nZ2VyOiB7XG4gICAgICAgIGRlYnVnOiAoZGF0YSkgPT4ge1xuICAgICAgICAgICAgY29uc29sZS5sb2coZGF0YSk7XG4gICAgICAgIH0sXG4gICAgICAgIGluZm86IChkYXRhKSA9PiB7XG4gICAgICAgICAgICBjb25zb2xlLmluZm8oZGF0YSk7XG4gICAgICAgIH0sXG4gICAgICAgIHdhcm46IChkYXRhKSA9PiB7XG4gICAgICAgICAgICBjb25zb2xlLndhcm4oZGF0YSk7XG4gICAgICAgIH0sXG4gICAgICAgIGVycm9yOiAoZGF0YSkgPT4ge1xuICAgICAgICAgICAgY29uc29sZS5lcnJvcihkYXRhKTtcbiAgICAgICAgfSxcbiAgICB9LFxuICAgIGV4dGVuZF9WMjogKCkgPT4ge1xuICAgICAgICAvLyBOby1vcCBpbiB0ZXN0IGVudmlyb25tZW50XG4gICAgfSxcbiAgICAvLyBAdHMtZXhwZWN0LWVycm9yIHdlIGFyZSBub3QgdXNpbmcgdGhlIHdvcmtlciBlbmRwb2ludCBpbiB0ZXN0cyBlbnYuXG4gICAgX191c2VFeHRlbnNpb25Db250ZXh0OiAoKSA9PiB7XG4gICAgICAgIC8vIE5vLW9wIGluIHRlc3QgZW52aXJvbm1lbnRcbiAgICB9LFxufTtcbi8qKlxuICogR2V0cyB0aGUgd29ya2VyIGdsb2JhbHMgb2JqZWN0IGZvciB0aGUgY3VycmVudCBlbnZpcm9ubWVudC5cbiAqIEByZXR1cm5zIFRoZSB3b3JrZXIgZ2xvYmFscyBvYmplY3QuXG4gKi9cbmV4cG9ydCBjb25zdCBnZXRXb3JrZXJHbG9iYWxzID0gKCkgPT4ge1xuICAgIHJldHVybiBpc1J1bm5pbmdJbldvcmtlcigpXG4gICAgICAgID8gc2VsZlxuICAgICAgICA6IGZha2VXb3JrZXJHbG9iYWxzO1xufTtcbiIsImltcG9ydCB7IGdldFdvcmtlckdsb2JhbHMgfSBmcm9tIFwiLi9pbnRlcm5hbC9nbG9iYWwtdXRpbHMuanNcIjtcbmNvbnN0IGV4dGVuZF9WMiA9IGdldFdvcmtlckdsb2JhbHMoKS5leHRlbmRfVjI7XG5leHBvcnQgZnVuY3Rpb24gc2VydmVybGVzcyhuYW1lLCBvcHRpb25zKSB7XG4gICAgcmV0dXJuIHNlbGYuc2VydmVybGVzcyhuYW1lLCBvcHRpb25zKTtcbn1cbmV4cG9ydCBmdW5jdGlvbiBmZXRjaCh1cmwsIG9wdGlvbnMpIHtcbiAgICByZXR1cm4gc2VsZi5oc0ZldGNoKHVybCwgb3B0aW9ucyk7XG59XG5leHBvcnQgY29uc3QgaHVic3BvdCA9IHtcbiAgICBleHRlbmQ6IGV4dGVuZF9WMixcbiAgICBzZXJ2ZXJsZXNzLFxuICAgIGZldGNoLFxufTtcbiIsIi8qKlxuICogQGNhdGVnb3J5IFNlcnZlcmxlc3NcbiAqL1xuZXhwb3J0IHZhciBTZXJ2ZXJsZXNzRXhlY3V0aW9uU3RhdHVzO1xuKGZ1bmN0aW9uIChTZXJ2ZXJsZXNzRXhlY3V0aW9uU3RhdHVzKSB7XG4gICAgU2VydmVybGVzc0V4ZWN1dGlvblN0YXR1c1tcIlN1Y2Nlc3NcIl0gPSBcIlNVQ0NFU1NcIjtcbiAgICBTZXJ2ZXJsZXNzRXhlY3V0aW9uU3RhdHVzW1wiRXJyb3JcIl0gPSBcIkVSUk9SXCI7XG59KShTZXJ2ZXJsZXNzRXhlY3V0aW9uU3RhdHVzIHx8IChTZXJ2ZXJsZXNzRXhlY3V0aW9uU3RhdHVzID0ge30pKTtcbiIsIi8qKlxuICogQGxpY2Vuc2UgUmVhY3RcbiAqIHJlYWN0LWpzeC1ydW50aW1lLmRldmVsb3BtZW50LmpzXG4gKlxuICogQ29weXJpZ2h0IChjKSBGYWNlYm9vaywgSW5jLiBhbmQgaXRzIGFmZmlsaWF0ZXMuXG4gKlxuICogVGhpcyBzb3VyY2UgY29kZSBpcyBsaWNlbnNlZCB1bmRlciB0aGUgTUlUIGxpY2Vuc2UgZm91bmQgaW4gdGhlXG4gKiBMSUNFTlNFIGZpbGUgaW4gdGhlIHJvb3QgZGlyZWN0b3J5IG9mIHRoaXMgc291cmNlIHRyZWUuXG4gKi9cblxuJ3VzZSBzdHJpY3QnO1xuXG5pZiAocHJvY2Vzcy5lbnYuTk9ERV9FTlYgIT09IFwicHJvZHVjdGlvblwiKSB7XG4gIChmdW5jdGlvbigpIHtcbid1c2Ugc3RyaWN0JztcblxudmFyIFJlYWN0ID0gcmVxdWlyZSgncmVhY3QnKTtcblxuLy8gQVRURU5USU9OXG4vLyBXaGVuIGFkZGluZyBuZXcgc3ltYm9scyB0byB0aGlzIGZpbGUsXG4vLyBQbGVhc2UgY29uc2lkZXIgYWxzbyBhZGRpbmcgdG8gJ3JlYWN0LWRldnRvb2xzLXNoYXJlZC9zcmMvYmFja2VuZC9SZWFjdFN5bWJvbHMnXG4vLyBUaGUgU3ltYm9sIHVzZWQgdG8gdGFnIHRoZSBSZWFjdEVsZW1lbnQtbGlrZSB0eXBlcy5cbnZhciBSRUFDVF9FTEVNRU5UX1RZUEUgPSBTeW1ib2wuZm9yKCdyZWFjdC5lbGVtZW50Jyk7XG52YXIgUkVBQ1RfUE9SVEFMX1RZUEUgPSBTeW1ib2wuZm9yKCdyZWFjdC5wb3J0YWwnKTtcbnZhciBSRUFDVF9GUkFHTUVOVF9UWVBFID0gU3ltYm9sLmZvcigncmVhY3QuZnJhZ21lbnQnKTtcbnZhciBSRUFDVF9TVFJJQ1RfTU9ERV9UWVBFID0gU3ltYm9sLmZvcigncmVhY3Quc3RyaWN0X21vZGUnKTtcbnZhciBSRUFDVF9QUk9GSUxFUl9UWVBFID0gU3ltYm9sLmZvcigncmVhY3QucHJvZmlsZXInKTtcbnZhciBSRUFDVF9QUk9WSURFUl9UWVBFID0gU3ltYm9sLmZvcigncmVhY3QucHJvdmlkZXInKTtcbnZhciBSRUFDVF9DT05URVhUX1RZUEUgPSBTeW1ib2wuZm9yKCdyZWFjdC5jb250ZXh0Jyk7XG52YXIgUkVBQ1RfRk9SV0FSRF9SRUZfVFlQRSA9IFN5bWJvbC5mb3IoJ3JlYWN0LmZvcndhcmRfcmVmJyk7XG52YXIgUkVBQ1RfU1VTUEVOU0VfVFlQRSA9IFN5bWJvbC5mb3IoJ3JlYWN0LnN1c3BlbnNlJyk7XG52YXIgUkVBQ1RfU1VTUEVOU0VfTElTVF9UWVBFID0gU3ltYm9sLmZvcigncmVhY3Quc3VzcGVuc2VfbGlzdCcpO1xudmFyIFJFQUNUX01FTU9fVFlQRSA9IFN5bWJvbC5mb3IoJ3JlYWN0Lm1lbW8nKTtcbnZhciBSRUFDVF9MQVpZX1RZUEUgPSBTeW1ib2wuZm9yKCdyZWFjdC5sYXp5Jyk7XG52YXIgUkVBQ1RfT0ZGU0NSRUVOX1RZUEUgPSBTeW1ib2wuZm9yKCdyZWFjdC5vZmZzY3JlZW4nKTtcbnZhciBNQVlCRV9JVEVSQVRPUl9TWU1CT0wgPSBTeW1ib2wuaXRlcmF0b3I7XG52YXIgRkFVWF9JVEVSQVRPUl9TWU1CT0wgPSAnQEBpdGVyYXRvcic7XG5mdW5jdGlvbiBnZXRJdGVyYXRvckZuKG1heWJlSXRlcmFibGUpIHtcbiAgaWYgKG1heWJlSXRlcmFibGUgPT09IG51bGwgfHwgdHlwZW9mIG1heWJlSXRlcmFibGUgIT09ICdvYmplY3QnKSB7XG4gICAgcmV0dXJuIG51bGw7XG4gIH1cblxuICB2YXIgbWF5YmVJdGVyYXRvciA9IE1BWUJFX0lURVJBVE9SX1NZTUJPTCAmJiBtYXliZUl0ZXJhYmxlW01BWUJFX0lURVJBVE9SX1NZTUJPTF0gfHwgbWF5YmVJdGVyYWJsZVtGQVVYX0lURVJBVE9SX1NZTUJPTF07XG5cbiAgaWYgKHR5cGVvZiBtYXliZUl0ZXJhdG9yID09PSAnZnVuY3Rpb24nKSB7XG4gICAgcmV0dXJuIG1heWJlSXRlcmF0b3I7XG4gIH1cblxuICByZXR1cm4gbnVsbDtcbn1cblxudmFyIFJlYWN0U2hhcmVkSW50ZXJuYWxzID0gUmVhY3QuX19TRUNSRVRfSU5URVJOQUxTX0RPX05PVF9VU0VfT1JfWU9VX1dJTExfQkVfRklSRUQ7XG5cbmZ1bmN0aW9uIGVycm9yKGZvcm1hdCkge1xuICB7XG4gICAge1xuICAgICAgZm9yICh2YXIgX2xlbjIgPSBhcmd1bWVudHMubGVuZ3RoLCBhcmdzID0gbmV3IEFycmF5KF9sZW4yID4gMSA/IF9sZW4yIC0gMSA6IDApLCBfa2V5MiA9IDE7IF9rZXkyIDwgX2xlbjI7IF9rZXkyKyspIHtcbiAgICAgICAgYXJnc1tfa2V5MiAtIDFdID0gYXJndW1lbnRzW19rZXkyXTtcbiAgICAgIH1cblxuICAgICAgcHJpbnRXYXJuaW5nKCdlcnJvcicsIGZvcm1hdCwgYXJncyk7XG4gICAgfVxuICB9XG59XG5cbmZ1bmN0aW9uIHByaW50V2FybmluZyhsZXZlbCwgZm9ybWF0LCBhcmdzKSB7XG4gIC8vIFdoZW4gY2hhbmdpbmcgdGhpcyBsb2dpYywgeW91IG1pZ2h0IHdhbnQgdG8gYWxzb1xuICAvLyB1cGRhdGUgY29uc29sZVdpdGhTdGFja0Rldi53d3cuanMgYXMgd2VsbC5cbiAge1xuICAgIHZhciBSZWFjdERlYnVnQ3VycmVudEZyYW1lID0gUmVhY3RTaGFyZWRJbnRlcm5hbHMuUmVhY3REZWJ1Z0N1cnJlbnRGcmFtZTtcbiAgICB2YXIgc3RhY2sgPSBSZWFjdERlYnVnQ3VycmVudEZyYW1lLmdldFN0YWNrQWRkZW5kdW0oKTtcblxuICAgIGlmIChzdGFjayAhPT0gJycpIHtcbiAgICAgIGZvcm1hdCArPSAnJXMnO1xuICAgICAgYXJncyA9IGFyZ3MuY29uY2F0KFtzdGFja10pO1xuICAgIH0gLy8gZXNsaW50LWRpc2FibGUtbmV4dC1saW5lIHJlYWN0LWludGVybmFsL3NhZmUtc3RyaW5nLWNvZXJjaW9uXG5cblxuICAgIHZhciBhcmdzV2l0aEZvcm1hdCA9IGFyZ3MubWFwKGZ1bmN0aW9uIChpdGVtKSB7XG4gICAgICByZXR1cm4gU3RyaW5nKGl0ZW0pO1xuICAgIH0pOyAvLyBDYXJlZnVsOiBSTiBjdXJyZW50bHkgZGVwZW5kcyBvbiB0aGlzIHByZWZpeFxuXG4gICAgYXJnc1dpdGhGb3JtYXQudW5zaGlmdCgnV2FybmluZzogJyArIGZvcm1hdCk7IC8vIFdlIGludGVudGlvbmFsbHkgZG9uJ3QgdXNlIHNwcmVhZCAob3IgLmFwcGx5KSBkaXJlY3RseSBiZWNhdXNlIGl0XG4gICAgLy8gYnJlYWtzIElFOTogaHR0cHM6Ly9naXRodWIuY29tL2ZhY2Vib29rL3JlYWN0L2lzc3Vlcy8xMzYxMFxuICAgIC8vIGVzbGludC1kaXNhYmxlLW5leHQtbGluZSByZWFjdC1pbnRlcm5hbC9uby1wcm9kdWN0aW9uLWxvZ2dpbmdcblxuICAgIEZ1bmN0aW9uLnByb3RvdHlwZS5hcHBseS5jYWxsKGNvbnNvbGVbbGV2ZWxdLCBjb25zb2xlLCBhcmdzV2l0aEZvcm1hdCk7XG4gIH1cbn1cblxuLy8gLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS1cblxudmFyIGVuYWJsZVNjb3BlQVBJID0gZmFsc2U7IC8vIEV4cGVyaW1lbnRhbCBDcmVhdGUgRXZlbnQgSGFuZGxlIEFQSS5cbnZhciBlbmFibGVDYWNoZUVsZW1lbnQgPSBmYWxzZTtcbnZhciBlbmFibGVUcmFuc2l0aW9uVHJhY2luZyA9IGZhbHNlOyAvLyBObyBrbm93biBidWdzLCBidXQgbmVlZHMgcGVyZm9ybWFuY2UgdGVzdGluZ1xuXG52YXIgZW5hYmxlTGVnYWN5SGlkZGVuID0gZmFsc2U7IC8vIEVuYWJsZXMgdW5zdGFibGVfYXZvaWRUaGlzRmFsbGJhY2sgZmVhdHVyZSBpbiBGaWJlclxuLy8gc3R1ZmYuIEludGVuZGVkIHRvIGVuYWJsZSBSZWFjdCBjb3JlIG1lbWJlcnMgdG8gbW9yZSBlYXNpbHkgZGVidWcgc2NoZWR1bGluZ1xuLy8gaXNzdWVzIGluIERFViBidWlsZHMuXG5cbnZhciBlbmFibGVEZWJ1Z1RyYWNpbmcgPSBmYWxzZTsgLy8gVHJhY2sgd2hpY2ggRmliZXIocykgc2NoZWR1bGUgcmVuZGVyIHdvcmsuXG5cbnZhciBSRUFDVF9NT0RVTEVfUkVGRVJFTkNFO1xuXG57XG4gIFJFQUNUX01PRFVMRV9SRUZFUkVOQ0UgPSBTeW1ib2wuZm9yKCdyZWFjdC5tb2R1bGUucmVmZXJlbmNlJyk7XG59XG5cbmZ1bmN0aW9uIGlzVmFsaWRFbGVtZW50VHlwZSh0eXBlKSB7XG4gIGlmICh0eXBlb2YgdHlwZSA9PT0gJ3N0cmluZycgfHwgdHlwZW9mIHR5cGUgPT09ICdmdW5jdGlvbicpIHtcbiAgICByZXR1cm4gdHJ1ZTtcbiAgfSAvLyBOb3RlOiB0eXBlb2YgbWlnaHQgYmUgb3RoZXIgdGhhbiAnc3ltYm9sJyBvciAnbnVtYmVyJyAoZS5nLiBpZiBpdCdzIGEgcG9seWZpbGwpLlxuXG5cbiAgaWYgKHR5cGUgPT09IFJFQUNUX0ZSQUdNRU5UX1RZUEUgfHwgdHlwZSA9PT0gUkVBQ1RfUFJPRklMRVJfVFlQRSB8fCBlbmFibGVEZWJ1Z1RyYWNpbmcgIHx8IHR5cGUgPT09IFJFQUNUX1NUUklDVF9NT0RFX1RZUEUgfHwgdHlwZSA9PT0gUkVBQ1RfU1VTUEVOU0VfVFlQRSB8fCB0eXBlID09PSBSRUFDVF9TVVNQRU5TRV9MSVNUX1RZUEUgfHwgZW5hYmxlTGVnYWN5SGlkZGVuICB8fCB0eXBlID09PSBSRUFDVF9PRkZTQ1JFRU5fVFlQRSB8fCBlbmFibGVTY29wZUFQSSAgfHwgZW5hYmxlQ2FjaGVFbGVtZW50ICB8fCBlbmFibGVUcmFuc2l0aW9uVHJhY2luZyApIHtcbiAgICByZXR1cm4gdHJ1ZTtcbiAgfVxuXG4gIGlmICh0eXBlb2YgdHlwZSA9PT0gJ29iamVjdCcgJiYgdHlwZSAhPT0gbnVsbCkge1xuICAgIGlmICh0eXBlLiQkdHlwZW9mID09PSBSRUFDVF9MQVpZX1RZUEUgfHwgdHlwZS4kJHR5cGVvZiA9PT0gUkVBQ1RfTUVNT19UWVBFIHx8IHR5cGUuJCR0eXBlb2YgPT09IFJFQUNUX1BST1ZJREVSX1RZUEUgfHwgdHlwZS4kJHR5cGVvZiA9PT0gUkVBQ1RfQ09OVEVYVF9UWVBFIHx8IHR5cGUuJCR0eXBlb2YgPT09IFJFQUNUX0ZPUldBUkRfUkVGX1RZUEUgfHwgLy8gVGhpcyBuZWVkcyB0byBpbmNsdWRlIGFsbCBwb3NzaWJsZSBtb2R1bGUgcmVmZXJlbmNlIG9iamVjdFxuICAgIC8vIHR5cGVzIHN1cHBvcnRlZCBieSBhbnkgRmxpZ2h0IGNvbmZpZ3VyYXRpb24gYW55d2hlcmUgc2luY2VcbiAgICAvLyB3ZSBkb24ndCBrbm93IHdoaWNoIEZsaWdodCBidWlsZCB0aGlzIHdpbGwgZW5kIHVwIGJlaW5nIHVzZWRcbiAgICAvLyB3aXRoLlxuICAgIHR5cGUuJCR0eXBlb2YgPT09IFJFQUNUX01PRFVMRV9SRUZFUkVOQ0UgfHwgdHlwZS5nZXRNb2R1bGVJZCAhPT0gdW5kZWZpbmVkKSB7XG4gICAgICByZXR1cm4gdHJ1ZTtcbiAgICB9XG4gIH1cblxuICByZXR1cm4gZmFsc2U7XG59XG5cbmZ1bmN0aW9uIGdldFdyYXBwZWROYW1lKG91dGVyVHlwZSwgaW5uZXJUeXBlLCB3cmFwcGVyTmFtZSkge1xuICB2YXIgZGlzcGxheU5hbWUgPSBvdXRlclR5cGUuZGlzcGxheU5hbWU7XG5cbiAgaWYgKGRpc3BsYXlOYW1lKSB7XG4gICAgcmV0dXJuIGRpc3BsYXlOYW1lO1xuICB9XG5cbiAgdmFyIGZ1bmN0aW9uTmFtZSA9IGlubmVyVHlwZS5kaXNwbGF5TmFtZSB8fCBpbm5lclR5cGUubmFtZSB8fCAnJztcbiAgcmV0dXJuIGZ1bmN0aW9uTmFtZSAhPT0gJycgPyB3cmFwcGVyTmFtZSArIFwiKFwiICsgZnVuY3Rpb25OYW1lICsgXCIpXCIgOiB3cmFwcGVyTmFtZTtcbn0gLy8gS2VlcCBpbiBzeW5jIHdpdGggcmVhY3QtcmVjb25jaWxlci9nZXRDb21wb25lbnROYW1lRnJvbUZpYmVyXG5cblxuZnVuY3Rpb24gZ2V0Q29udGV4dE5hbWUodHlwZSkge1xuICByZXR1cm4gdHlwZS5kaXNwbGF5TmFtZSB8fCAnQ29udGV4dCc7XG59IC8vIE5vdGUgdGhhdCB0aGUgcmVjb25jaWxlciBwYWNrYWdlIHNob3VsZCBnZW5lcmFsbHkgcHJlZmVyIHRvIHVzZSBnZXRDb21wb25lbnROYW1lRnJvbUZpYmVyKCkgaW5zdGVhZC5cblxuXG5mdW5jdGlvbiBnZXRDb21wb25lbnROYW1lRnJvbVR5cGUodHlwZSkge1xuICBpZiAodHlwZSA9PSBudWxsKSB7XG4gICAgLy8gSG9zdCByb290LCB0ZXh0IG5vZGUgb3IganVzdCBpbnZhbGlkIHR5cGUuXG4gICAgcmV0dXJuIG51bGw7XG4gIH1cblxuICB7XG4gICAgaWYgKHR5cGVvZiB0eXBlLnRhZyA9PT0gJ251bWJlcicpIHtcbiAgICAgIGVycm9yKCdSZWNlaXZlZCBhbiB1bmV4cGVjdGVkIG9iamVjdCBpbiBnZXRDb21wb25lbnROYW1lRnJvbVR5cGUoKS4gJyArICdUaGlzIGlzIGxpa2VseSBhIGJ1ZyBpbiBSZWFjdC4gUGxlYXNlIGZpbGUgYW4gaXNzdWUuJyk7XG4gICAgfVxuICB9XG5cbiAgaWYgKHR5cGVvZiB0eXBlID09PSAnZnVuY3Rpb24nKSB7XG4gICAgcmV0dXJuIHR5cGUuZGlzcGxheU5hbWUgfHwgdHlwZS5uYW1lIHx8IG51bGw7XG4gIH1cblxuICBpZiAodHlwZW9mIHR5cGUgPT09ICdzdHJpbmcnKSB7XG4gICAgcmV0dXJuIHR5cGU7XG4gIH1cblxuICBzd2l0Y2ggKHR5cGUpIHtcbiAgICBjYXNlIFJFQUNUX0ZSQUdNRU5UX1RZUEU6XG4gICAgICByZXR1cm4gJ0ZyYWdtZW50JztcblxuICAgIGNhc2UgUkVBQ1RfUE9SVEFMX1RZUEU6XG4gICAgICByZXR1cm4gJ1BvcnRhbCc7XG5cbiAgICBjYXNlIFJFQUNUX1BST0ZJTEVSX1RZUEU6XG4gICAgICByZXR1cm4gJ1Byb2ZpbGVyJztcblxuICAgIGNhc2UgUkVBQ1RfU1RSSUNUX01PREVfVFlQRTpcbiAgICAgIHJldHVybiAnU3RyaWN0TW9kZSc7XG5cbiAgICBjYXNlIFJFQUNUX1NVU1BFTlNFX1RZUEU6XG4gICAgICByZXR1cm4gJ1N1c3BlbnNlJztcblxuICAgIGNhc2UgUkVBQ1RfU1VTUEVOU0VfTElTVF9UWVBFOlxuICAgICAgcmV0dXJuICdTdXNwZW5zZUxpc3QnO1xuXG4gIH1cblxuICBpZiAodHlwZW9mIHR5cGUgPT09ICdvYmplY3QnKSB7XG4gICAgc3dpdGNoICh0eXBlLiQkdHlwZW9mKSB7XG4gICAgICBjYXNlIFJFQUNUX0NPTlRFWFRfVFlQRTpcbiAgICAgICAgdmFyIGNvbnRleHQgPSB0eXBlO1xuICAgICAgICByZXR1cm4gZ2V0Q29udGV4dE5hbWUoY29udGV4dCkgKyAnLkNvbnN1bWVyJztcblxuICAgICAgY2FzZSBSRUFDVF9QUk9WSURFUl9UWVBFOlxuICAgICAgICB2YXIgcHJvdmlkZXIgPSB0eXBlO1xuICAgICAgICByZXR1cm4gZ2V0Q29udGV4dE5hbWUocHJvdmlkZXIuX2NvbnRleHQpICsgJy5Qcm92aWRlcic7XG5cbiAgICAgIGNhc2UgUkVBQ1RfRk9SV0FSRF9SRUZfVFlQRTpcbiAgICAgICAgcmV0dXJuIGdldFdyYXBwZWROYW1lKHR5cGUsIHR5cGUucmVuZGVyLCAnRm9yd2FyZFJlZicpO1xuXG4gICAgICBjYXNlIFJFQUNUX01FTU9fVFlQRTpcbiAgICAgICAgdmFyIG91dGVyTmFtZSA9IHR5cGUuZGlzcGxheU5hbWUgfHwgbnVsbDtcblxuICAgICAgICBpZiAob3V0ZXJOYW1lICE9PSBudWxsKSB7XG4gICAgICAgICAgcmV0dXJuIG91dGVyTmFtZTtcbiAgICAgICAgfVxuXG4gICAgICAgIHJldHVybiBnZXRDb21wb25lbnROYW1lRnJvbVR5cGUodHlwZS50eXBlKSB8fCAnTWVtbyc7XG5cbiAgICAgIGNhc2UgUkVBQ1RfTEFaWV9UWVBFOlxuICAgICAgICB7XG4gICAgICAgICAgdmFyIGxhenlDb21wb25lbnQgPSB0eXBlO1xuICAgICAgICAgIHZhciBwYXlsb2FkID0gbGF6eUNvbXBvbmVudC5fcGF5bG9hZDtcbiAgICAgICAgICB2YXIgaW5pdCA9IGxhenlDb21wb25lbnQuX2luaXQ7XG5cbiAgICAgICAgICB0cnkge1xuICAgICAgICAgICAgcmV0dXJuIGdldENvbXBvbmVudE5hbWVGcm9tVHlwZShpbml0KHBheWxvYWQpKTtcbiAgICAgICAgICB9IGNhdGNoICh4KSB7XG4gICAgICAgICAgICByZXR1cm4gbnVsbDtcbiAgICAgICAgICB9XG4gICAgICAgIH1cblxuICAgICAgLy8gZXNsaW50LWRpc2FibGUtbmV4dC1saW5lIG5vLWZhbGx0aHJvdWdoXG4gICAgfVxuICB9XG5cbiAgcmV0dXJuIG51bGw7XG59XG5cbnZhciBhc3NpZ24gPSBPYmplY3QuYXNzaWduO1xuXG4vLyBIZWxwZXJzIHRvIHBhdGNoIGNvbnNvbGUubG9ncyB0byBhdm9pZCBsb2dnaW5nIGR1cmluZyBzaWRlLWVmZmVjdCBmcmVlXG4vLyByZXBsYXlpbmcgb24gcmVuZGVyIGZ1bmN0aW9uLiBUaGlzIGN1cnJlbnRseSBvbmx5IHBhdGNoZXMgdGhlIG9iamVjdFxuLy8gbGF6aWx5IHdoaWNoIHdvbid0IGNvdmVyIGlmIHRoZSBsb2cgZnVuY3Rpb24gd2FzIGV4dHJhY3RlZCBlYWdlcmx5LlxuLy8gV2UgY291bGQgYWxzbyBlYWdlcmx5IHBhdGNoIHRoZSBtZXRob2QuXG52YXIgZGlzYWJsZWREZXB0aCA9IDA7XG52YXIgcHJldkxvZztcbnZhciBwcmV2SW5mbztcbnZhciBwcmV2V2FybjtcbnZhciBwcmV2RXJyb3I7XG52YXIgcHJldkdyb3VwO1xudmFyIHByZXZHcm91cENvbGxhcHNlZDtcbnZhciBwcmV2R3JvdXBFbmQ7XG5cbmZ1bmN0aW9uIGRpc2FibGVkTG9nKCkge31cblxuZGlzYWJsZWRMb2cuX19yZWFjdERpc2FibGVkTG9nID0gdHJ1ZTtcbmZ1bmN0aW9uIGRpc2FibGVMb2dzKCkge1xuICB7XG4gICAgaWYgKGRpc2FibGVkRGVwdGggPT09IDApIHtcbiAgICAgIC8qIGVzbGludC1kaXNhYmxlIHJlYWN0LWludGVybmFsL25vLXByb2R1Y3Rpb24tbG9nZ2luZyAqL1xuICAgICAgcHJldkxvZyA9IGNvbnNvbGUubG9nO1xuICAgICAgcHJldkluZm8gPSBjb25zb2xlLmluZm87XG4gICAgICBwcmV2V2FybiA9IGNvbnNvbGUud2FybjtcbiAgICAgIHByZXZFcnJvciA9IGNvbnNvbGUuZXJyb3I7XG4gICAgICBwcmV2R3JvdXAgPSBjb25zb2xlLmdyb3VwO1xuICAgICAgcHJldkdyb3VwQ29sbGFwc2VkID0gY29uc29sZS5ncm91cENvbGxhcHNlZDtcbiAgICAgIHByZXZHcm91cEVuZCA9IGNvbnNvbGUuZ3JvdXBFbmQ7IC8vIGh0dHBzOi8vZ2l0aHViLmNvbS9mYWNlYm9vay9yZWFjdC9pc3N1ZXMvMTkwOTlcblxuICAgICAgdmFyIHByb3BzID0ge1xuICAgICAgICBjb25maWd1cmFibGU6IHRydWUsXG4gICAgICAgIGVudW1lcmFibGU6IHRydWUsXG4gICAgICAgIHZhbHVlOiBkaXNhYmxlZExvZyxcbiAgICAgICAgd3JpdGFibGU6IHRydWVcbiAgICAgIH07IC8vICRGbG93Rml4TWUgRmxvdyB0aGlua3MgY29uc29sZSBpcyBpbW11dGFibGUuXG5cbiAgICAgIE9iamVjdC5kZWZpbmVQcm9wZXJ0aWVzKGNvbnNvbGUsIHtcbiAgICAgICAgaW5mbzogcHJvcHMsXG4gICAgICAgIGxvZzogcHJvcHMsXG4gICAgICAgIHdhcm46IHByb3BzLFxuICAgICAgICBlcnJvcjogcHJvcHMsXG4gICAgICAgIGdyb3VwOiBwcm9wcyxcbiAgICAgICAgZ3JvdXBDb2xsYXBzZWQ6IHByb3BzLFxuICAgICAgICBncm91cEVuZDogcHJvcHNcbiAgICAgIH0pO1xuICAgICAgLyogZXNsaW50LWVuYWJsZSByZWFjdC1pbnRlcm5hbC9uby1wcm9kdWN0aW9uLWxvZ2dpbmcgKi9cbiAgICB9XG5cbiAgICBkaXNhYmxlZERlcHRoKys7XG4gIH1cbn1cbmZ1bmN0aW9uIHJlZW5hYmxlTG9ncygpIHtcbiAge1xuICAgIGRpc2FibGVkRGVwdGgtLTtcblxuICAgIGlmIChkaXNhYmxlZERlcHRoID09PSAwKSB7XG4gICAgICAvKiBlc2xpbnQtZGlzYWJsZSByZWFjdC1pbnRlcm5hbC9uby1wcm9kdWN0aW9uLWxvZ2dpbmcgKi9cbiAgICAgIHZhciBwcm9wcyA9IHtcbiAgICAgICAgY29uZmlndXJhYmxlOiB0cnVlLFxuICAgICAgICBlbnVtZXJhYmxlOiB0cnVlLFxuICAgICAgICB3cml0YWJsZTogdHJ1ZVxuICAgICAgfTsgLy8gJEZsb3dGaXhNZSBGbG93IHRoaW5rcyBjb25zb2xlIGlzIGltbXV0YWJsZS5cblxuICAgICAgT2JqZWN0LmRlZmluZVByb3BlcnRpZXMoY29uc29sZSwge1xuICAgICAgICBsb2c6IGFzc2lnbih7fSwgcHJvcHMsIHtcbiAgICAgICAgICB2YWx1ZTogcHJldkxvZ1xuICAgICAgICB9KSxcbiAgICAgICAgaW5mbzogYXNzaWduKHt9LCBwcm9wcywge1xuICAgICAgICAgIHZhbHVlOiBwcmV2SW5mb1xuICAgICAgICB9KSxcbiAgICAgICAgd2FybjogYXNzaWduKHt9LCBwcm9wcywge1xuICAgICAgICAgIHZhbHVlOiBwcmV2V2FyblxuICAgICAgICB9KSxcbiAgICAgICAgZXJyb3I6IGFzc2lnbih7fSwgcHJvcHMsIHtcbiAgICAgICAgICB2YWx1ZTogcHJldkVycm9yXG4gICAgICAgIH0pLFxuICAgICAgICBncm91cDogYXNzaWduKHt9LCBwcm9wcywge1xuICAgICAgICAgIHZhbHVlOiBwcmV2R3JvdXBcbiAgICAgICAgfSksXG4gICAgICAgIGdyb3VwQ29sbGFwc2VkOiBhc3NpZ24oe30sIHByb3BzLCB7XG4gICAgICAgICAgdmFsdWU6IHByZXZHcm91cENvbGxhcHNlZFxuICAgICAgICB9KSxcbiAgICAgICAgZ3JvdXBFbmQ6IGFzc2lnbih7fSwgcHJvcHMsIHtcbiAgICAgICAgICB2YWx1ZTogcHJldkdyb3VwRW5kXG4gICAgICAgIH0pXG4gICAgICB9KTtcbiAgICAgIC8qIGVzbGludC1lbmFibGUgcmVhY3QtaW50ZXJuYWwvbm8tcHJvZHVjdGlvbi1sb2dnaW5nICovXG4gICAgfVxuXG4gICAgaWYgKGRpc2FibGVkRGVwdGggPCAwKSB7XG4gICAgICBlcnJvcignZGlzYWJsZWREZXB0aCBmZWxsIGJlbG93IHplcm8uICcgKyAnVGhpcyBpcyBhIGJ1ZyBpbiBSZWFjdC4gUGxlYXNlIGZpbGUgYW4gaXNzdWUuJyk7XG4gICAgfVxuICB9XG59XG5cbnZhciBSZWFjdEN1cnJlbnREaXNwYXRjaGVyID0gUmVhY3RTaGFyZWRJbnRlcm5hbHMuUmVhY3RDdXJyZW50RGlzcGF0Y2hlcjtcbnZhciBwcmVmaXg7XG5mdW5jdGlvbiBkZXNjcmliZUJ1aWx0SW5Db21wb25lbnRGcmFtZShuYW1lLCBzb3VyY2UsIG93bmVyRm4pIHtcbiAge1xuICAgIGlmIChwcmVmaXggPT09IHVuZGVmaW5lZCkge1xuICAgICAgLy8gRXh0cmFjdCB0aGUgVk0gc3BlY2lmaWMgcHJlZml4IHVzZWQgYnkgZWFjaCBsaW5lLlxuICAgICAgdHJ5IHtcbiAgICAgICAgdGhyb3cgRXJyb3IoKTtcbiAgICAgIH0gY2F0Y2ggKHgpIHtcbiAgICAgICAgdmFyIG1hdGNoID0geC5zdGFjay50cmltKCkubWF0Y2goL1xcbiggKihhdCApPykvKTtcbiAgICAgICAgcHJlZml4ID0gbWF0Y2ggJiYgbWF0Y2hbMV0gfHwgJyc7XG4gICAgICB9XG4gICAgfSAvLyBXZSB1c2UgdGhlIHByZWZpeCB0byBlbnN1cmUgb3VyIHN0YWNrcyBsaW5lIHVwIHdpdGggbmF0aXZlIHN0YWNrIGZyYW1lcy5cblxuXG4gICAgcmV0dXJuICdcXG4nICsgcHJlZml4ICsgbmFtZTtcbiAgfVxufVxudmFyIHJlZW50cnkgPSBmYWxzZTtcbnZhciBjb21wb25lbnRGcmFtZUNhY2hlO1xuXG57XG4gIHZhciBQb3NzaWJseVdlYWtNYXAgPSB0eXBlb2YgV2Vha01hcCA9PT0gJ2Z1bmN0aW9uJyA/IFdlYWtNYXAgOiBNYXA7XG4gIGNvbXBvbmVudEZyYW1lQ2FjaGUgPSBuZXcgUG9zc2libHlXZWFrTWFwKCk7XG59XG5cbmZ1bmN0aW9uIGRlc2NyaWJlTmF0aXZlQ29tcG9uZW50RnJhbWUoZm4sIGNvbnN0cnVjdCkge1xuICAvLyBJZiBzb21ldGhpbmcgYXNrZWQgZm9yIGEgc3RhY2sgaW5zaWRlIGEgZmFrZSByZW5kZXIsIGl0IHNob3VsZCBnZXQgaWdub3JlZC5cbiAgaWYgKCAhZm4gfHwgcmVlbnRyeSkge1xuICAgIHJldHVybiAnJztcbiAgfVxuXG4gIHtcbiAgICB2YXIgZnJhbWUgPSBjb21wb25lbnRGcmFtZUNhY2hlLmdldChmbik7XG5cbiAgICBpZiAoZnJhbWUgIT09IHVuZGVmaW5lZCkge1xuICAgICAgcmV0dXJuIGZyYW1lO1xuICAgIH1cbiAgfVxuXG4gIHZhciBjb250cm9sO1xuICByZWVudHJ5ID0gdHJ1ZTtcbiAgdmFyIHByZXZpb3VzUHJlcGFyZVN0YWNrVHJhY2UgPSBFcnJvci5wcmVwYXJlU3RhY2tUcmFjZTsgLy8gJEZsb3dGaXhNZSBJdCBkb2VzIGFjY2VwdCB1bmRlZmluZWQuXG5cbiAgRXJyb3IucHJlcGFyZVN0YWNrVHJhY2UgPSB1bmRlZmluZWQ7XG4gIHZhciBwcmV2aW91c0Rpc3BhdGNoZXI7XG5cbiAge1xuICAgIHByZXZpb3VzRGlzcGF0Y2hlciA9IFJlYWN0Q3VycmVudERpc3BhdGNoZXIuY3VycmVudDsgLy8gU2V0IHRoZSBkaXNwYXRjaGVyIGluIERFViBiZWNhdXNlIHRoaXMgbWlnaHQgYmUgY2FsbCBpbiB0aGUgcmVuZGVyIGZ1bmN0aW9uXG4gICAgLy8gZm9yIHdhcm5pbmdzLlxuXG4gICAgUmVhY3RDdXJyZW50RGlzcGF0Y2hlci5jdXJyZW50ID0gbnVsbDtcbiAgICBkaXNhYmxlTG9ncygpO1xuICB9XG5cbiAgdHJ5IHtcbiAgICAvLyBUaGlzIHNob3VsZCB0aHJvdy5cbiAgICBpZiAoY29uc3RydWN0KSB7XG4gICAgICAvLyBTb21ldGhpbmcgc2hvdWxkIGJlIHNldHRpbmcgdGhlIHByb3BzIGluIHRoZSBjb25zdHJ1Y3Rvci5cbiAgICAgIHZhciBGYWtlID0gZnVuY3Rpb24gKCkge1xuICAgICAgICB0aHJvdyBFcnJvcigpO1xuICAgICAgfTsgLy8gJEZsb3dGaXhNZVxuXG5cbiAgICAgIE9iamVjdC5kZWZpbmVQcm9wZXJ0eShGYWtlLnByb3RvdHlwZSwgJ3Byb3BzJywge1xuICAgICAgICBzZXQ6IGZ1bmN0aW9uICgpIHtcbiAgICAgICAgICAvLyBXZSB1c2UgYSB0aHJvd2luZyBzZXR0ZXIgaW5zdGVhZCBvZiBmcm96ZW4gb3Igbm9uLXdyaXRhYmxlIHByb3BzXG4gICAgICAgICAgLy8gYmVjYXVzZSB0aGF0IHdvbid0IHRocm93IGluIGEgbm9uLXN0cmljdCBtb2RlIGZ1bmN0aW9uLlxuICAgICAgICAgIHRocm93IEVycm9yKCk7XG4gICAgICAgIH1cbiAgICAgIH0pO1xuXG4gICAgICBpZiAodHlwZW9mIFJlZmxlY3QgPT09ICdvYmplY3QnICYmIFJlZmxlY3QuY29uc3RydWN0KSB7XG4gICAgICAgIC8vIFdlIGNvbnN0cnVjdCBhIGRpZmZlcmVudCBjb250cm9sIGZvciB0aGlzIGNhc2UgdG8gaW5jbHVkZSBhbnkgZXh0cmFcbiAgICAgICAgLy8gZnJhbWVzIGFkZGVkIGJ5IHRoZSBjb25zdHJ1Y3QgY2FsbC5cbiAgICAgICAgdHJ5IHtcbiAgICAgICAgICBSZWZsZWN0LmNvbnN0cnVjdChGYWtlLCBbXSk7XG4gICAgICAgIH0gY2F0Y2ggKHgpIHtcbiAgICAgICAgICBjb250cm9sID0geDtcbiAgICAgICAgfVxuXG4gICAgICAgIFJlZmxlY3QuY29uc3RydWN0KGZuLCBbXSwgRmFrZSk7XG4gICAgICB9IGVsc2Uge1xuICAgICAgICB0cnkge1xuICAgICAgICAgIEZha2UuY2FsbCgpO1xuICAgICAgICB9IGNhdGNoICh4KSB7XG4gICAgICAgICAgY29udHJvbCA9IHg7XG4gICAgICAgIH1cblxuICAgICAgICBmbi5jYWxsKEZha2UucHJvdG90eXBlKTtcbiAgICAgIH1cbiAgICB9IGVsc2Uge1xuICAgICAgdHJ5IHtcbiAgICAgICAgdGhyb3cgRXJyb3IoKTtcbiAgICAgIH0gY2F0Y2ggKHgpIHtcbiAgICAgICAgY29udHJvbCA9IHg7XG4gICAgICB9XG5cbiAgICAgIGZuKCk7XG4gICAgfVxuICB9IGNhdGNoIChzYW1wbGUpIHtcbiAgICAvLyBUaGlzIGlzIGlubGluZWQgbWFudWFsbHkgYmVjYXVzZSBjbG9zdXJlIGRvZXNuJ3QgZG8gaXQgZm9yIHVzLlxuICAgIGlmIChzYW1wbGUgJiYgY29udHJvbCAmJiB0eXBlb2Ygc2FtcGxlLnN0YWNrID09PSAnc3RyaW5nJykge1xuICAgICAgLy8gVGhpcyBleHRyYWN0cyB0aGUgZmlyc3QgZnJhbWUgZnJvbSB0aGUgc2FtcGxlIHRoYXQgaXNuJ3QgYWxzbyBpbiB0aGUgY29udHJvbC5cbiAgICAgIC8vIFNraXBwaW5nIG9uZSBmcmFtZSB0aGF0IHdlIGFzc3VtZSBpcyB0aGUgZnJhbWUgdGhhdCBjYWxscyB0aGUgdHdvLlxuICAgICAgdmFyIHNhbXBsZUxpbmVzID0gc2FtcGxlLnN0YWNrLnNwbGl0KCdcXG4nKTtcbiAgICAgIHZhciBjb250cm9sTGluZXMgPSBjb250cm9sLnN0YWNrLnNwbGl0KCdcXG4nKTtcbiAgICAgIHZhciBzID0gc2FtcGxlTGluZXMubGVuZ3RoIC0gMTtcbiAgICAgIHZhciBjID0gY29udHJvbExpbmVzLmxlbmd0aCAtIDE7XG5cbiAgICAgIHdoaWxlIChzID49IDEgJiYgYyA+PSAwICYmIHNhbXBsZUxpbmVzW3NdICE9PSBjb250cm9sTGluZXNbY10pIHtcbiAgICAgICAgLy8gV2UgZXhwZWN0IGF0IGxlYXN0IG9uZSBzdGFjayBmcmFtZSB0byBiZSBzaGFyZWQuXG4gICAgICAgIC8vIFR5cGljYWxseSB0aGlzIHdpbGwgYmUgdGhlIHJvb3QgbW9zdCBvbmUuIEhvd2V2ZXIsIHN0YWNrIGZyYW1lcyBtYXkgYmVcbiAgICAgICAgLy8gY3V0IG9mZiBkdWUgdG8gbWF4aW11bSBzdGFjayBsaW1pdHMuIEluIHRoaXMgY2FzZSwgb25lIG1heWJlIGN1dCBvZmZcbiAgICAgICAgLy8gZWFybGllciB0aGFuIHRoZSBvdGhlci4gV2UgYXNzdW1lIHRoYXQgdGhlIHNhbXBsZSBpcyBsb25nZXIgb3IgdGhlIHNhbWVcbiAgICAgICAgLy8gYW5kIHRoZXJlIGZvciBjdXQgb2ZmIGVhcmxpZXIuIFNvIHdlIHNob3VsZCBmaW5kIHRoZSByb290IG1vc3QgZnJhbWUgaW5cbiAgICAgICAgLy8gdGhlIHNhbXBsZSBzb21ld2hlcmUgaW4gdGhlIGNvbnRyb2wuXG4gICAgICAgIGMtLTtcbiAgICAgIH1cblxuICAgICAgZm9yICg7IHMgPj0gMSAmJiBjID49IDA7IHMtLSwgYy0tKSB7XG4gICAgICAgIC8vIE5leHQgd2UgZmluZCB0aGUgZmlyc3Qgb25lIHRoYXQgaXNuJ3QgdGhlIHNhbWUgd2hpY2ggc2hvdWxkIGJlIHRoZVxuICAgICAgICAvLyBmcmFtZSB0aGF0IGNhbGxlZCBvdXIgc2FtcGxlIGZ1bmN0aW9uIGFuZCB0aGUgY29udHJvbC5cbiAgICAgICAgaWYgKHNhbXBsZUxpbmVzW3NdICE9PSBjb250cm9sTGluZXNbY10pIHtcbiAgICAgICAgICAvLyBJbiBWOCwgdGhlIGZpcnN0IGxpbmUgaXMgZGVzY3JpYmluZyB0aGUgbWVzc2FnZSBidXQgb3RoZXIgVk1zIGRvbid0LlxuICAgICAgICAgIC8vIElmIHdlJ3JlIGFib3V0IHRvIHJldHVybiB0aGUgZmlyc3QgbGluZSwgYW5kIHRoZSBjb250cm9sIGlzIGFsc28gb24gdGhlIHNhbWVcbiAgICAgICAgICAvLyBsaW5lLCB0aGF0J3MgYSBwcmV0dHkgZ29vZCBpbmRpY2F0b3IgdGhhdCBvdXIgc2FtcGxlIHRocmV3IGF0IHNhbWUgbGluZSBhc1xuICAgICAgICAgIC8vIHRoZSBjb250cm9sLiBJLmUuIGJlZm9yZSB3ZSBlbnRlcmVkIHRoZSBzYW1wbGUgZnJhbWUuIFNvIHdlIGlnbm9yZSB0aGlzIHJlc3VsdC5cbiAgICAgICAgICAvLyBUaGlzIGNhbiBoYXBwZW4gaWYgeW91IHBhc3NlZCBhIGNsYXNzIHRvIGZ1bmN0aW9uIGNvbXBvbmVudCwgb3Igbm9uLWZ1bmN0aW9uLlxuICAgICAgICAgIGlmIChzICE9PSAxIHx8IGMgIT09IDEpIHtcbiAgICAgICAgICAgIGRvIHtcbiAgICAgICAgICAgICAgcy0tO1xuICAgICAgICAgICAgICBjLS07IC8vIFdlIG1heSBzdGlsbCBoYXZlIHNpbWlsYXIgaW50ZXJtZWRpYXRlIGZyYW1lcyBmcm9tIHRoZSBjb25zdHJ1Y3QgY2FsbC5cbiAgICAgICAgICAgICAgLy8gVGhlIG5leHQgb25lIHRoYXQgaXNuJ3QgdGhlIHNhbWUgc2hvdWxkIGJlIG91ciBtYXRjaCB0aG91Z2guXG5cbiAgICAgICAgICAgICAgaWYgKGMgPCAwIHx8IHNhbXBsZUxpbmVzW3NdICE9PSBjb250cm9sTGluZXNbY10pIHtcbiAgICAgICAgICAgICAgICAvLyBWOCBhZGRzIGEgXCJuZXdcIiBwcmVmaXggZm9yIG5hdGl2ZSBjbGFzc2VzLiBMZXQncyByZW1vdmUgaXQgdG8gbWFrZSBpdCBwcmV0dGllci5cbiAgICAgICAgICAgICAgICB2YXIgX2ZyYW1lID0gJ1xcbicgKyBzYW1wbGVMaW5lc1tzXS5yZXBsYWNlKCcgYXQgbmV3ICcsICcgYXQgJyk7IC8vIElmIG91ciBjb21wb25lbnQgZnJhbWUgaXMgbGFiZWxlZCBcIjxhbm9ueW1vdXM+XCJcbiAgICAgICAgICAgICAgICAvLyBidXQgd2UgaGF2ZSBhIHVzZXItcHJvdmlkZWQgXCJkaXNwbGF5TmFtZVwiXG4gICAgICAgICAgICAgICAgLy8gc3BsaWNlIGl0IGluIHRvIG1ha2UgdGhlIHN0YWNrIG1vcmUgcmVhZGFibGUuXG5cblxuICAgICAgICAgICAgICAgIGlmIChmbi5kaXNwbGF5TmFtZSAmJiBfZnJhbWUuaW5jbHVkZXMoJzxhbm9ueW1vdXM+JykpIHtcbiAgICAgICAgICAgICAgICAgIF9mcmFtZSA9IF9mcmFtZS5yZXBsYWNlKCc8YW5vbnltb3VzPicsIGZuLmRpc3BsYXlOYW1lKTtcbiAgICAgICAgICAgICAgICB9XG5cbiAgICAgICAgICAgICAgICB7XG4gICAgICAgICAgICAgICAgICBpZiAodHlwZW9mIGZuID09PSAnZnVuY3Rpb24nKSB7XG4gICAgICAgICAgICAgICAgICAgIGNvbXBvbmVudEZyYW1lQ2FjaGUuc2V0KGZuLCBfZnJhbWUpO1xuICAgICAgICAgICAgICAgICAgfVxuICAgICAgICAgICAgICAgIH0gLy8gUmV0dXJuIHRoZSBsaW5lIHdlIGZvdW5kLlxuXG5cbiAgICAgICAgICAgICAgICByZXR1cm4gX2ZyYW1lO1xuICAgICAgICAgICAgICB9XG4gICAgICAgICAgICB9IHdoaWxlIChzID49IDEgJiYgYyA+PSAwKTtcbiAgICAgICAgICB9XG5cbiAgICAgICAgICBicmVhaztcbiAgICAgICAgfVxuICAgICAgfVxuICAgIH1cbiAgfSBmaW5hbGx5IHtcbiAgICByZWVudHJ5ID0gZmFsc2U7XG5cbiAgICB7XG4gICAgICBSZWFjdEN1cnJlbnREaXNwYXRjaGVyLmN1cnJlbnQgPSBwcmV2aW91c0Rpc3BhdGNoZXI7XG4gICAgICByZWVuYWJsZUxvZ3MoKTtcbiAgICB9XG5cbiAgICBFcnJvci5wcmVwYXJlU3RhY2tUcmFjZSA9IHByZXZpb3VzUHJlcGFyZVN0YWNrVHJhY2U7XG4gIH0gLy8gRmFsbGJhY2sgdG8ganVzdCB1c2luZyB0aGUgbmFtZSBpZiB3ZSBjb3VsZG4ndCBtYWtlIGl0IHRocm93LlxuXG5cbiAgdmFyIG5hbWUgPSBmbiA/IGZuLmRpc3BsYXlOYW1lIHx8IGZuLm5hbWUgOiAnJztcbiAgdmFyIHN5bnRoZXRpY0ZyYW1lID0gbmFtZSA/IGRlc2NyaWJlQnVpbHRJbkNvbXBvbmVudEZyYW1lKG5hbWUpIDogJyc7XG5cbiAge1xuICAgIGlmICh0eXBlb2YgZm4gPT09ICdmdW5jdGlvbicpIHtcbiAgICAgIGNvbXBvbmVudEZyYW1lQ2FjaGUuc2V0KGZuLCBzeW50aGV0aWNGcmFtZSk7XG4gICAgfVxuICB9XG5cbiAgcmV0dXJuIHN5bnRoZXRpY0ZyYW1lO1xufVxuZnVuY3Rpb24gZGVzY3JpYmVGdW5jdGlvbkNvbXBvbmVudEZyYW1lKGZuLCBzb3VyY2UsIG93bmVyRm4pIHtcbiAge1xuICAgIHJldHVybiBkZXNjcmliZU5hdGl2ZUNvbXBvbmVudEZyYW1lKGZuLCBmYWxzZSk7XG4gIH1cbn1cblxuZnVuY3Rpb24gc2hvdWxkQ29uc3RydWN0KENvbXBvbmVudCkge1xuICB2YXIgcHJvdG90eXBlID0gQ29tcG9uZW50LnByb3RvdHlwZTtcbiAgcmV0dXJuICEhKHByb3RvdHlwZSAmJiBwcm90b3R5cGUuaXNSZWFjdENvbXBvbmVudCk7XG59XG5cbmZ1bmN0aW9uIGRlc2NyaWJlVW5rbm93bkVsZW1lbnRUeXBlRnJhbWVJbkRFVih0eXBlLCBzb3VyY2UsIG93bmVyRm4pIHtcblxuICBpZiAodHlwZSA9PSBudWxsKSB7XG4gICAgcmV0dXJuICcnO1xuICB9XG5cbiAgaWYgKHR5cGVvZiB0eXBlID09PSAnZnVuY3Rpb24nKSB7XG4gICAge1xuICAgICAgcmV0dXJuIGRlc2NyaWJlTmF0aXZlQ29tcG9uZW50RnJhbWUodHlwZSwgc2hvdWxkQ29uc3RydWN0KHR5cGUpKTtcbiAgICB9XG4gIH1cblxuICBpZiAodHlwZW9mIHR5cGUgPT09ICdzdHJpbmcnKSB7XG4gICAgcmV0dXJuIGRlc2NyaWJlQnVpbHRJbkNvbXBvbmVudEZyYW1lKHR5cGUpO1xuICB9XG5cbiAgc3dpdGNoICh0eXBlKSB7XG4gICAgY2FzZSBSRUFDVF9TVVNQRU5TRV9UWVBFOlxuICAgICAgcmV0dXJuIGRlc2NyaWJlQnVpbHRJbkNvbXBvbmVudEZyYW1lKCdTdXNwZW5zZScpO1xuXG4gICAgY2FzZSBSRUFDVF9TVVNQRU5TRV9MSVNUX1RZUEU6XG4gICAgICByZXR1cm4gZGVzY3JpYmVCdWlsdEluQ29tcG9uZW50RnJhbWUoJ1N1c3BlbnNlTGlzdCcpO1xuICB9XG5cbiAgaWYgKHR5cGVvZiB0eXBlID09PSAnb2JqZWN0Jykge1xuICAgIHN3aXRjaCAodHlwZS4kJHR5cGVvZikge1xuICAgICAgY2FzZSBSRUFDVF9GT1JXQVJEX1JFRl9UWVBFOlxuICAgICAgICByZXR1cm4gZGVzY3JpYmVGdW5jdGlvbkNvbXBvbmVudEZyYW1lKHR5cGUucmVuZGVyKTtcblxuICAgICAgY2FzZSBSRUFDVF9NRU1PX1RZUEU6XG4gICAgICAgIC8vIE1lbW8gbWF5IGNvbnRhaW4gYW55IGNvbXBvbmVudCB0eXBlIHNvIHdlIHJlY3Vyc2l2ZWx5IHJlc29sdmUgaXQuXG4gICAgICAgIHJldHVybiBkZXNjcmliZVVua25vd25FbGVtZW50VHlwZUZyYW1lSW5ERVYodHlwZS50eXBlLCBzb3VyY2UsIG93bmVyRm4pO1xuXG4gICAgICBjYXNlIFJFQUNUX0xBWllfVFlQRTpcbiAgICAgICAge1xuICAgICAgICAgIHZhciBsYXp5Q29tcG9uZW50ID0gdHlwZTtcbiAgICAgICAgICB2YXIgcGF5bG9hZCA9IGxhenlDb21wb25lbnQuX3BheWxvYWQ7XG4gICAgICAgICAgdmFyIGluaXQgPSBsYXp5Q29tcG9uZW50Ll9pbml0O1xuXG4gICAgICAgICAgdHJ5IHtcbiAgICAgICAgICAgIC8vIExhenkgbWF5IGNvbnRhaW4gYW55IGNvbXBvbmVudCB0eXBlIHNvIHdlIHJlY3Vyc2l2ZWx5IHJlc29sdmUgaXQuXG4gICAgICAgICAgICByZXR1cm4gZGVzY3JpYmVVbmtub3duRWxlbWVudFR5cGVGcmFtZUluREVWKGluaXQocGF5bG9hZCksIHNvdXJjZSwgb3duZXJGbik7XG4gICAgICAgICAgfSBjYXRjaCAoeCkge31cbiAgICAgICAgfVxuICAgIH1cbiAgfVxuXG4gIHJldHVybiAnJztcbn1cblxudmFyIGhhc093blByb3BlcnR5ID0gT2JqZWN0LnByb3RvdHlwZS5oYXNPd25Qcm9wZXJ0eTtcblxudmFyIGxvZ2dlZFR5cGVGYWlsdXJlcyA9IHt9O1xudmFyIFJlYWN0RGVidWdDdXJyZW50RnJhbWUgPSBSZWFjdFNoYXJlZEludGVybmFscy5SZWFjdERlYnVnQ3VycmVudEZyYW1lO1xuXG5mdW5jdGlvbiBzZXRDdXJyZW50bHlWYWxpZGF0aW5nRWxlbWVudChlbGVtZW50KSB7XG4gIHtcbiAgICBpZiAoZWxlbWVudCkge1xuICAgICAgdmFyIG93bmVyID0gZWxlbWVudC5fb3duZXI7XG4gICAgICB2YXIgc3RhY2sgPSBkZXNjcmliZVVua25vd25FbGVtZW50VHlwZUZyYW1lSW5ERVYoZWxlbWVudC50eXBlLCBlbGVtZW50Ll9zb3VyY2UsIG93bmVyID8gb3duZXIudHlwZSA6IG51bGwpO1xuICAgICAgUmVhY3REZWJ1Z0N1cnJlbnRGcmFtZS5zZXRFeHRyYVN0YWNrRnJhbWUoc3RhY2spO1xuICAgIH0gZWxzZSB7XG4gICAgICBSZWFjdERlYnVnQ3VycmVudEZyYW1lLnNldEV4dHJhU3RhY2tGcmFtZShudWxsKTtcbiAgICB9XG4gIH1cbn1cblxuZnVuY3Rpb24gY2hlY2tQcm9wVHlwZXModHlwZVNwZWNzLCB2YWx1ZXMsIGxvY2F0aW9uLCBjb21wb25lbnROYW1lLCBlbGVtZW50KSB7XG4gIHtcbiAgICAvLyAkRmxvd0ZpeE1lIFRoaXMgaXMgb2theSBidXQgRmxvdyBkb2Vzbid0IGtub3cgaXQuXG4gICAgdmFyIGhhcyA9IEZ1bmN0aW9uLmNhbGwuYmluZChoYXNPd25Qcm9wZXJ0eSk7XG5cbiAgICBmb3IgKHZhciB0eXBlU3BlY05hbWUgaW4gdHlwZVNwZWNzKSB7XG4gICAgICBpZiAoaGFzKHR5cGVTcGVjcywgdHlwZVNwZWNOYW1lKSkge1xuICAgICAgICB2YXIgZXJyb3IkMSA9IHZvaWQgMDsgLy8gUHJvcCB0eXBlIHZhbGlkYXRpb24gbWF5IHRocm93LiBJbiBjYXNlIHRoZXkgZG8sIHdlIGRvbid0IHdhbnQgdG9cbiAgICAgICAgLy8gZmFpbCB0aGUgcmVuZGVyIHBoYXNlIHdoZXJlIGl0IGRpZG4ndCBmYWlsIGJlZm9yZS4gU28gd2UgbG9nIGl0LlxuICAgICAgICAvLyBBZnRlciB0aGVzZSBoYXZlIGJlZW4gY2xlYW5lZCB1cCwgd2UnbGwgbGV0IHRoZW0gdGhyb3cuXG5cbiAgICAgICAgdHJ5IHtcbiAgICAgICAgICAvLyBUaGlzIGlzIGludGVudGlvbmFsbHkgYW4gaW52YXJpYW50IHRoYXQgZ2V0cyBjYXVnaHQuIEl0J3MgdGhlIHNhbWVcbiAgICAgICAgICAvLyBiZWhhdmlvciBhcyB3aXRob3V0IHRoaXMgc3RhdGVtZW50IGV4Y2VwdCB3aXRoIGEgYmV0dGVyIG1lc3NhZ2UuXG4gICAgICAgICAgaWYgKHR5cGVvZiB0eXBlU3BlY3NbdHlwZVNwZWNOYW1lXSAhPT0gJ2Z1bmN0aW9uJykge1xuICAgICAgICAgICAgLy8gZXNsaW50LWRpc2FibGUtbmV4dC1saW5lIHJlYWN0LWludGVybmFsL3Byb2QtZXJyb3ItY29kZXNcbiAgICAgICAgICAgIHZhciBlcnIgPSBFcnJvcigoY29tcG9uZW50TmFtZSB8fCAnUmVhY3QgY2xhc3MnKSArICc6ICcgKyBsb2NhdGlvbiArICcgdHlwZSBgJyArIHR5cGVTcGVjTmFtZSArICdgIGlzIGludmFsaWQ7ICcgKyAnaXQgbXVzdCBiZSBhIGZ1bmN0aW9uLCB1c3VhbGx5IGZyb20gdGhlIGBwcm9wLXR5cGVzYCBwYWNrYWdlLCBidXQgcmVjZWl2ZWQgYCcgKyB0eXBlb2YgdHlwZVNwZWNzW3R5cGVTcGVjTmFtZV0gKyAnYC4nICsgJ1RoaXMgb2Z0ZW4gaGFwcGVucyBiZWNhdXNlIG9mIHR5cG9zIHN1Y2ggYXMgYFByb3BUeXBlcy5mdW5jdGlvbmAgaW5zdGVhZCBvZiBgUHJvcFR5cGVzLmZ1bmNgLicpO1xuICAgICAgICAgICAgZXJyLm5hbWUgPSAnSW52YXJpYW50IFZpb2xhdGlvbic7XG4gICAgICAgICAgICB0aHJvdyBlcnI7XG4gICAgICAgICAgfVxuXG4gICAgICAgICAgZXJyb3IkMSA9IHR5cGVTcGVjc1t0eXBlU3BlY05hbWVdKHZhbHVlcywgdHlwZVNwZWNOYW1lLCBjb21wb25lbnROYW1lLCBsb2NhdGlvbiwgbnVsbCwgJ1NFQ1JFVF9ET19OT1RfUEFTU19USElTX09SX1lPVV9XSUxMX0JFX0ZJUkVEJyk7XG4gICAgICAgIH0gY2F0Y2ggKGV4KSB7XG4gICAgICAgICAgZXJyb3IkMSA9IGV4O1xuICAgICAgICB9XG5cbiAgICAgICAgaWYgKGVycm9yJDEgJiYgIShlcnJvciQxIGluc3RhbmNlb2YgRXJyb3IpKSB7XG4gICAgICAgICAgc2V0Q3VycmVudGx5VmFsaWRhdGluZ0VsZW1lbnQoZWxlbWVudCk7XG5cbiAgICAgICAgICBlcnJvcignJXM6IHR5cGUgc3BlY2lmaWNhdGlvbiBvZiAlcycgKyAnIGAlc2AgaXMgaW52YWxpZDsgdGhlIHR5cGUgY2hlY2tlciAnICsgJ2Z1bmN0aW9uIG11c3QgcmV0dXJuIGBudWxsYCBvciBhbiBgRXJyb3JgIGJ1dCByZXR1cm5lZCBhICVzLiAnICsgJ1lvdSBtYXkgaGF2ZSBmb3Jnb3R0ZW4gdG8gcGFzcyBhbiBhcmd1bWVudCB0byB0aGUgdHlwZSBjaGVja2VyICcgKyAnY3JlYXRvciAoYXJyYXlPZiwgaW5zdGFuY2VPZiwgb2JqZWN0T2YsIG9uZU9mLCBvbmVPZlR5cGUsIGFuZCAnICsgJ3NoYXBlIGFsbCByZXF1aXJlIGFuIGFyZ3VtZW50KS4nLCBjb21wb25lbnROYW1lIHx8ICdSZWFjdCBjbGFzcycsIGxvY2F0aW9uLCB0eXBlU3BlY05hbWUsIHR5cGVvZiBlcnJvciQxKTtcblxuICAgICAgICAgIHNldEN1cnJlbnRseVZhbGlkYXRpbmdFbGVtZW50KG51bGwpO1xuICAgICAgICB9XG5cbiAgICAgICAgaWYgKGVycm9yJDEgaW5zdGFuY2VvZiBFcnJvciAmJiAhKGVycm9yJDEubWVzc2FnZSBpbiBsb2dnZWRUeXBlRmFpbHVyZXMpKSB7XG4gICAgICAgICAgLy8gT25seSBtb25pdG9yIHRoaXMgZmFpbHVyZSBvbmNlIGJlY2F1c2UgdGhlcmUgdGVuZHMgdG8gYmUgYSBsb3Qgb2YgdGhlXG4gICAgICAgICAgLy8gc2FtZSBlcnJvci5cbiAgICAgICAgICBsb2dnZWRUeXBlRmFpbHVyZXNbZXJyb3IkMS5tZXNzYWdlXSA9IHRydWU7XG4gICAgICAgICAgc2V0Q3VycmVudGx5VmFsaWRhdGluZ0VsZW1lbnQoZWxlbWVudCk7XG5cbiAgICAgICAgICBlcnJvcignRmFpbGVkICVzIHR5cGU6ICVzJywgbG9jYXRpb24sIGVycm9yJDEubWVzc2FnZSk7XG5cbiAgICAgICAgICBzZXRDdXJyZW50bHlWYWxpZGF0aW5nRWxlbWVudChudWxsKTtcbiAgICAgICAgfVxuICAgICAgfVxuICAgIH1cbiAgfVxufVxuXG52YXIgaXNBcnJheUltcGwgPSBBcnJheS5pc0FycmF5OyAvLyBlc2xpbnQtZGlzYWJsZS1uZXh0LWxpbmUgbm8tcmVkZWNsYXJlXG5cbmZ1bmN0aW9uIGlzQXJyYXkoYSkge1xuICByZXR1cm4gaXNBcnJheUltcGwoYSk7XG59XG5cbi8qXG4gKiBUaGUgYCcnICsgdmFsdWVgIHBhdHRlcm4gKHVzZWQgaW4gaW4gcGVyZi1zZW5zaXRpdmUgY29kZSkgdGhyb3dzIGZvciBTeW1ib2xcbiAqIGFuZCBUZW1wb3JhbC4qIHR5cGVzLiBTZWUgaHR0cHM6Ly9naXRodWIuY29tL2ZhY2Vib29rL3JlYWN0L3B1bGwvMjIwNjQuXG4gKlxuICogVGhlIGZ1bmN0aW9ucyBpbiB0aGlzIG1vZHVsZSB3aWxsIHRocm93IGFuIGVhc2llci10by11bmRlcnN0YW5kLFxuICogZWFzaWVyLXRvLWRlYnVnIGV4Y2VwdGlvbiB3aXRoIGEgY2xlYXIgZXJyb3JzIG1lc3NhZ2UgbWVzc2FnZSBleHBsYWluaW5nIHRoZVxuICogcHJvYmxlbS4gKEluc3RlYWQgb2YgYSBjb25mdXNpbmcgZXhjZXB0aW9uIHRocm93biBpbnNpZGUgdGhlIGltcGxlbWVudGF0aW9uXG4gKiBvZiB0aGUgYHZhbHVlYCBvYmplY3QpLlxuICovXG4vLyAkRmxvd0ZpeE1lIG9ubHkgY2FsbGVkIGluIERFViwgc28gdm9pZCByZXR1cm4gaXMgbm90IHBvc3NpYmxlLlxuZnVuY3Rpb24gdHlwZU5hbWUodmFsdWUpIHtcbiAge1xuICAgIC8vIHRvU3RyaW5nVGFnIGlzIG5lZWRlZCBmb3IgbmFtZXNwYWNlZCB0eXBlcyBsaWtlIFRlbXBvcmFsLkluc3RhbnRcbiAgICB2YXIgaGFzVG9TdHJpbmdUYWcgPSB0eXBlb2YgU3ltYm9sID09PSAnZnVuY3Rpb24nICYmIFN5bWJvbC50b1N0cmluZ1RhZztcbiAgICB2YXIgdHlwZSA9IGhhc1RvU3RyaW5nVGFnICYmIHZhbHVlW1N5bWJvbC50b1N0cmluZ1RhZ10gfHwgdmFsdWUuY29uc3RydWN0b3IubmFtZSB8fCAnT2JqZWN0JztcbiAgICByZXR1cm4gdHlwZTtcbiAgfVxufSAvLyAkRmxvd0ZpeE1lIG9ubHkgY2FsbGVkIGluIERFViwgc28gdm9pZCByZXR1cm4gaXMgbm90IHBvc3NpYmxlLlxuXG5cbmZ1bmN0aW9uIHdpbGxDb2VyY2lvblRocm93KHZhbHVlKSB7XG4gIHtcbiAgICB0cnkge1xuICAgICAgdGVzdFN0cmluZ0NvZXJjaW9uKHZhbHVlKTtcbiAgICAgIHJldHVybiBmYWxzZTtcbiAgICB9IGNhdGNoIChlKSB7XG4gICAgICByZXR1cm4gdHJ1ZTtcbiAgICB9XG4gIH1cbn1cblxuZnVuY3Rpb24gdGVzdFN0cmluZ0NvZXJjaW9uKHZhbHVlKSB7XG4gIC8vIElmIHlvdSBlbmRlZCB1cCBoZXJlIGJ5IGZvbGxvd2luZyBhbiBleGNlcHRpb24gY2FsbCBzdGFjaywgaGVyZSdzIHdoYXQnc1xuICAvLyBoYXBwZW5lZDogeW91IHN1cHBsaWVkIGFuIG9iamVjdCBvciBzeW1ib2wgdmFsdWUgdG8gUmVhY3QgKGFzIGEgcHJvcCwga2V5LFxuICAvLyBET00gYXR0cmlidXRlLCBDU1MgcHJvcGVydHksIHN0cmluZyByZWYsIGV0Yy4pIGFuZCB3aGVuIFJlYWN0IHRyaWVkIHRvXG4gIC8vIGNvZXJjZSBpdCB0byBhIHN0cmluZyB1c2luZyBgJycgKyB2YWx1ZWAsIGFuIGV4Y2VwdGlvbiB3YXMgdGhyb3duLlxuICAvL1xuICAvLyBUaGUgbW9zdCBjb21tb24gdHlwZXMgdGhhdCB3aWxsIGNhdXNlIHRoaXMgZXhjZXB0aW9uIGFyZSBgU3ltYm9sYCBpbnN0YW5jZXNcbiAgLy8gYW5kIFRlbXBvcmFsIG9iamVjdHMgbGlrZSBgVGVtcG9yYWwuSW5zdGFudGAuIEJ1dCBhbnkgb2JqZWN0IHRoYXQgaGFzIGFcbiAgLy8gYHZhbHVlT2ZgIG9yIGBbU3ltYm9sLnRvUHJpbWl0aXZlXWAgbWV0aG9kIHRoYXQgdGhyb3dzIHdpbGwgYWxzbyBjYXVzZSB0aGlzXG4gIC8vIGV4Y2VwdGlvbi4gKExpYnJhcnkgYXV0aG9ycyBkbyB0aGlzIHRvIHByZXZlbnQgdXNlcnMgZnJvbSB1c2luZyBidWlsdC1pblxuICAvLyBudW1lcmljIG9wZXJhdG9ycyBsaWtlIGArYCBvciBjb21wYXJpc29uIG9wZXJhdG9ycyBsaWtlIGA+PWAgYmVjYXVzZSBjdXN0b21cbiAgLy8gbWV0aG9kcyBhcmUgbmVlZGVkIHRvIHBlcmZvcm0gYWNjdXJhdGUgYXJpdGhtZXRpYyBvciBjb21wYXJpc29uLilcbiAgLy9cbiAgLy8gVG8gZml4IHRoZSBwcm9ibGVtLCBjb2VyY2UgdGhpcyBvYmplY3Qgb3Igc3ltYm9sIHZhbHVlIHRvIGEgc3RyaW5nIGJlZm9yZVxuICAvLyBwYXNzaW5nIGl0IHRvIFJlYWN0LiBUaGUgbW9zdCByZWxpYWJsZSB3YXkgaXMgdXN1YWxseSBgU3RyaW5nKHZhbHVlKWAuXG4gIC8vXG4gIC8vIFRvIGZpbmQgd2hpY2ggdmFsdWUgaXMgdGhyb3dpbmcsIGNoZWNrIHRoZSBicm93c2VyIG9yIGRlYnVnZ2VyIGNvbnNvbGUuXG4gIC8vIEJlZm9yZSB0aGlzIGV4Y2VwdGlvbiB3YXMgdGhyb3duLCB0aGVyZSBzaG91bGQgYmUgYGNvbnNvbGUuZXJyb3JgIG91dHB1dFxuICAvLyB0aGF0IHNob3dzIHRoZSB0eXBlIChTeW1ib2wsIFRlbXBvcmFsLlBsYWluRGF0ZSwgZXRjLikgdGhhdCBjYXVzZWQgdGhlXG4gIC8vIHByb2JsZW0gYW5kIGhvdyB0aGF0IHR5cGUgd2FzIHVzZWQ6IGtleSwgYXRycmlidXRlLCBpbnB1dCB2YWx1ZSBwcm9wLCBldGMuXG4gIC8vIEluIG1vc3QgY2FzZXMsIHRoaXMgY29uc29sZSBvdXRwdXQgYWxzbyBzaG93cyB0aGUgY29tcG9uZW50IGFuZCBpdHNcbiAgLy8gYW5jZXN0b3IgY29tcG9uZW50cyB3aGVyZSB0aGUgZXhjZXB0aW9uIGhhcHBlbmVkLlxuICAvL1xuICAvLyBlc2xpbnQtZGlzYWJsZS1uZXh0LWxpbmUgcmVhY3QtaW50ZXJuYWwvc2FmZS1zdHJpbmctY29lcmNpb25cbiAgcmV0dXJuICcnICsgdmFsdWU7XG59XG5mdW5jdGlvbiBjaGVja0tleVN0cmluZ0NvZXJjaW9uKHZhbHVlKSB7XG4gIHtcbiAgICBpZiAod2lsbENvZXJjaW9uVGhyb3codmFsdWUpKSB7XG4gICAgICBlcnJvcignVGhlIHByb3ZpZGVkIGtleSBpcyBhbiB1bnN1cHBvcnRlZCB0eXBlICVzLicgKyAnIFRoaXMgdmFsdWUgbXVzdCBiZSBjb2VyY2VkIHRvIGEgc3RyaW5nIGJlZm9yZSBiZWZvcmUgdXNpbmcgaXQgaGVyZS4nLCB0eXBlTmFtZSh2YWx1ZSkpO1xuXG4gICAgICByZXR1cm4gdGVzdFN0cmluZ0NvZXJjaW9uKHZhbHVlKTsgLy8gdGhyb3cgKHRvIGhlbHAgY2FsbGVycyBmaW5kIHRyb3VibGVzaG9vdGluZyBjb21tZW50cylcbiAgICB9XG4gIH1cbn1cblxudmFyIFJlYWN0Q3VycmVudE93bmVyID0gUmVhY3RTaGFyZWRJbnRlcm5hbHMuUmVhY3RDdXJyZW50T3duZXI7XG52YXIgUkVTRVJWRURfUFJPUFMgPSB7XG4gIGtleTogdHJ1ZSxcbiAgcmVmOiB0cnVlLFxuICBfX3NlbGY6IHRydWUsXG4gIF9fc291cmNlOiB0cnVlXG59O1xudmFyIHNwZWNpYWxQcm9wS2V5V2FybmluZ1Nob3duO1xudmFyIHNwZWNpYWxQcm9wUmVmV2FybmluZ1Nob3duO1xudmFyIGRpZFdhcm5BYm91dFN0cmluZ1JlZnM7XG5cbntcbiAgZGlkV2FybkFib3V0U3RyaW5nUmVmcyA9IHt9O1xufVxuXG5mdW5jdGlvbiBoYXNWYWxpZFJlZihjb25maWcpIHtcbiAge1xuICAgIGlmIChoYXNPd25Qcm9wZXJ0eS5jYWxsKGNvbmZpZywgJ3JlZicpKSB7XG4gICAgICB2YXIgZ2V0dGVyID0gT2JqZWN0LmdldE93blByb3BlcnR5RGVzY3JpcHRvcihjb25maWcsICdyZWYnKS5nZXQ7XG5cbiAgICAgIGlmIChnZXR0ZXIgJiYgZ2V0dGVyLmlzUmVhY3RXYXJuaW5nKSB7XG4gICAgICAgIHJldHVybiBmYWxzZTtcbiAgICAgIH1cbiAgICB9XG4gIH1cblxuICByZXR1cm4gY29uZmlnLnJlZiAhPT0gdW5kZWZpbmVkO1xufVxuXG5mdW5jdGlvbiBoYXNWYWxpZEtleShjb25maWcpIHtcbiAge1xuICAgIGlmIChoYXNPd25Qcm9wZXJ0eS5jYWxsKGNvbmZpZywgJ2tleScpKSB7XG4gICAgICB2YXIgZ2V0dGVyID0gT2JqZWN0LmdldE93blByb3BlcnR5RGVzY3JpcHRvcihjb25maWcsICdrZXknKS5nZXQ7XG5cbiAgICAgIGlmIChnZXR0ZXIgJiYgZ2V0dGVyLmlzUmVhY3RXYXJuaW5nKSB7XG4gICAgICAgIHJldHVybiBmYWxzZTtcbiAgICAgIH1cbiAgICB9XG4gIH1cblxuICByZXR1cm4gY29uZmlnLmtleSAhPT0gdW5kZWZpbmVkO1xufVxuXG5mdW5jdGlvbiB3YXJuSWZTdHJpbmdSZWZDYW5ub3RCZUF1dG9Db252ZXJ0ZWQoY29uZmlnLCBzZWxmKSB7XG4gIHtcbiAgICBpZiAodHlwZW9mIGNvbmZpZy5yZWYgPT09ICdzdHJpbmcnICYmIFJlYWN0Q3VycmVudE93bmVyLmN1cnJlbnQgJiYgc2VsZiAmJiBSZWFjdEN1cnJlbnRPd25lci5jdXJyZW50LnN0YXRlTm9kZSAhPT0gc2VsZikge1xuICAgICAgdmFyIGNvbXBvbmVudE5hbWUgPSBnZXRDb21wb25lbnROYW1lRnJvbVR5cGUoUmVhY3RDdXJyZW50T3duZXIuY3VycmVudC50eXBlKTtcblxuICAgICAgaWYgKCFkaWRXYXJuQWJvdXRTdHJpbmdSZWZzW2NvbXBvbmVudE5hbWVdKSB7XG4gICAgICAgIGVycm9yKCdDb21wb25lbnQgXCIlc1wiIGNvbnRhaW5zIHRoZSBzdHJpbmcgcmVmIFwiJXNcIi4gJyArICdTdXBwb3J0IGZvciBzdHJpbmcgcmVmcyB3aWxsIGJlIHJlbW92ZWQgaW4gYSBmdXR1cmUgbWFqb3IgcmVsZWFzZS4gJyArICdUaGlzIGNhc2UgY2Fubm90IGJlIGF1dG9tYXRpY2FsbHkgY29udmVydGVkIHRvIGFuIGFycm93IGZ1bmN0aW9uLiAnICsgJ1dlIGFzayB5b3UgdG8gbWFudWFsbHkgZml4IHRoaXMgY2FzZSBieSB1c2luZyB1c2VSZWYoKSBvciBjcmVhdGVSZWYoKSBpbnN0ZWFkLiAnICsgJ0xlYXJuIG1vcmUgYWJvdXQgdXNpbmcgcmVmcyBzYWZlbHkgaGVyZTogJyArICdodHRwczovL3JlYWN0anMub3JnL2xpbmsvc3RyaWN0LW1vZGUtc3RyaW5nLXJlZicsIGdldENvbXBvbmVudE5hbWVGcm9tVHlwZShSZWFjdEN1cnJlbnRPd25lci5jdXJyZW50LnR5cGUpLCBjb25maWcucmVmKTtcblxuICAgICAgICBkaWRXYXJuQWJvdXRTdHJpbmdSZWZzW2NvbXBvbmVudE5hbWVdID0gdHJ1ZTtcbiAgICAgIH1cbiAgICB9XG4gIH1cbn1cblxuZnVuY3Rpb24gZGVmaW5lS2V5UHJvcFdhcm5pbmdHZXR0ZXIocHJvcHMsIGRpc3BsYXlOYW1lKSB7XG4gIHtcbiAgICB2YXIgd2FybkFib3V0QWNjZXNzaW5nS2V5ID0gZnVuY3Rpb24gKCkge1xuICAgICAgaWYgKCFzcGVjaWFsUHJvcEtleVdhcm5pbmdTaG93bikge1xuICAgICAgICBzcGVjaWFsUHJvcEtleVdhcm5pbmdTaG93biA9IHRydWU7XG5cbiAgICAgICAgZXJyb3IoJyVzOiBga2V5YCBpcyBub3QgYSBwcm9wLiBUcnlpbmcgdG8gYWNjZXNzIGl0IHdpbGwgcmVzdWx0ICcgKyAnaW4gYHVuZGVmaW5lZGAgYmVpbmcgcmV0dXJuZWQuIElmIHlvdSBuZWVkIHRvIGFjY2VzcyB0aGUgc2FtZSAnICsgJ3ZhbHVlIHdpdGhpbiB0aGUgY2hpbGQgY29tcG9uZW50LCB5b3Ugc2hvdWxkIHBhc3MgaXQgYXMgYSBkaWZmZXJlbnQgJyArICdwcm9wLiAoaHR0cHM6Ly9yZWFjdGpzLm9yZy9saW5rL3NwZWNpYWwtcHJvcHMpJywgZGlzcGxheU5hbWUpO1xuICAgICAgfVxuICAgIH07XG5cbiAgICB3YXJuQWJvdXRBY2Nlc3NpbmdLZXkuaXNSZWFjdFdhcm5pbmcgPSB0cnVlO1xuICAgIE9iamVjdC5kZWZpbmVQcm9wZXJ0eShwcm9wcywgJ2tleScsIHtcbiAgICAgIGdldDogd2FybkFib3V0QWNjZXNzaW5nS2V5LFxuICAgICAgY29uZmlndXJhYmxlOiB0cnVlXG4gICAgfSk7XG4gIH1cbn1cblxuZnVuY3Rpb24gZGVmaW5lUmVmUHJvcFdhcm5pbmdHZXR0ZXIocHJvcHMsIGRpc3BsYXlOYW1lKSB7XG4gIHtcbiAgICB2YXIgd2FybkFib3V0QWNjZXNzaW5nUmVmID0gZnVuY3Rpb24gKCkge1xuICAgICAgaWYgKCFzcGVjaWFsUHJvcFJlZldhcm5pbmdTaG93bikge1xuICAgICAgICBzcGVjaWFsUHJvcFJlZldhcm5pbmdTaG93biA9IHRydWU7XG5cbiAgICAgICAgZXJyb3IoJyVzOiBgcmVmYCBpcyBub3QgYSBwcm9wLiBUcnlpbmcgdG8gYWNjZXNzIGl0IHdpbGwgcmVzdWx0ICcgKyAnaW4gYHVuZGVmaW5lZGAgYmVpbmcgcmV0dXJuZWQuIElmIHlvdSBuZWVkIHRvIGFjY2VzcyB0aGUgc2FtZSAnICsgJ3ZhbHVlIHdpdGhpbiB0aGUgY2hpbGQgY29tcG9uZW50LCB5b3Ugc2hvdWxkIHBhc3MgaXQgYXMgYSBkaWZmZXJlbnQgJyArICdwcm9wLiAoaHR0cHM6Ly9yZWFjdGpzLm9yZy9saW5rL3NwZWNpYWwtcHJvcHMpJywgZGlzcGxheU5hbWUpO1xuICAgICAgfVxuICAgIH07XG5cbiAgICB3YXJuQWJvdXRBY2Nlc3NpbmdSZWYuaXNSZWFjdFdhcm5pbmcgPSB0cnVlO1xuICAgIE9iamVjdC5kZWZpbmVQcm9wZXJ0eShwcm9wcywgJ3JlZicsIHtcbiAgICAgIGdldDogd2FybkFib3V0QWNjZXNzaW5nUmVmLFxuICAgICAgY29uZmlndXJhYmxlOiB0cnVlXG4gICAgfSk7XG4gIH1cbn1cbi8qKlxuICogRmFjdG9yeSBtZXRob2QgdG8gY3JlYXRlIGEgbmV3IFJlYWN0IGVsZW1lbnQuIFRoaXMgbm8gbG9uZ2VyIGFkaGVyZXMgdG9cbiAqIHRoZSBjbGFzcyBwYXR0ZXJuLCBzbyBkbyBub3QgdXNlIG5ldyB0byBjYWxsIGl0LiBBbHNvLCBpbnN0YW5jZW9mIGNoZWNrXG4gKiB3aWxsIG5vdCB3b3JrLiBJbnN0ZWFkIHRlc3QgJCR0eXBlb2YgZmllbGQgYWdhaW5zdCBTeW1ib2wuZm9yKCdyZWFjdC5lbGVtZW50JykgdG8gY2hlY2tcbiAqIGlmIHNvbWV0aGluZyBpcyBhIFJlYWN0IEVsZW1lbnQuXG4gKlxuICogQHBhcmFtIHsqfSB0eXBlXG4gKiBAcGFyYW0geyp9IHByb3BzXG4gKiBAcGFyYW0geyp9IGtleVxuICogQHBhcmFtIHtzdHJpbmd8b2JqZWN0fSByZWZcbiAqIEBwYXJhbSB7Kn0gb3duZXJcbiAqIEBwYXJhbSB7Kn0gc2VsZiBBICp0ZW1wb3JhcnkqIGhlbHBlciB0byBkZXRlY3QgcGxhY2VzIHdoZXJlIGB0aGlzYCBpc1xuICogZGlmZmVyZW50IGZyb20gdGhlIGBvd25lcmAgd2hlbiBSZWFjdC5jcmVhdGVFbGVtZW50IGlzIGNhbGxlZCwgc28gdGhhdCB3ZVxuICogY2FuIHdhcm4uIFdlIHdhbnQgdG8gZ2V0IHJpZCBvZiBvd25lciBhbmQgcmVwbGFjZSBzdHJpbmcgYHJlZmBzIHdpdGggYXJyb3dcbiAqIGZ1bmN0aW9ucywgYW5kIGFzIGxvbmcgYXMgYHRoaXNgIGFuZCBvd25lciBhcmUgdGhlIHNhbWUsIHRoZXJlIHdpbGwgYmUgbm9cbiAqIGNoYW5nZSBpbiBiZWhhdmlvci5cbiAqIEBwYXJhbSB7Kn0gc291cmNlIEFuIGFubm90YXRpb24gb2JqZWN0IChhZGRlZCBieSBhIHRyYW5zcGlsZXIgb3Igb3RoZXJ3aXNlKVxuICogaW5kaWNhdGluZyBmaWxlbmFtZSwgbGluZSBudW1iZXIsIGFuZC9vciBvdGhlciBpbmZvcm1hdGlvbi5cbiAqIEBpbnRlcm5hbFxuICovXG5cblxudmFyIFJlYWN0RWxlbWVudCA9IGZ1bmN0aW9uICh0eXBlLCBrZXksIHJlZiwgc2VsZiwgc291cmNlLCBvd25lciwgcHJvcHMpIHtcbiAgdmFyIGVsZW1lbnQgPSB7XG4gICAgLy8gVGhpcyB0YWcgYWxsb3dzIHVzIHRvIHVuaXF1ZWx5IGlkZW50aWZ5IHRoaXMgYXMgYSBSZWFjdCBFbGVtZW50XG4gICAgJCR0eXBlb2Y6IFJFQUNUX0VMRU1FTlRfVFlQRSxcbiAgICAvLyBCdWlsdC1pbiBwcm9wZXJ0aWVzIHRoYXQgYmVsb25nIG9uIHRoZSBlbGVtZW50XG4gICAgdHlwZTogdHlwZSxcbiAgICBrZXk6IGtleSxcbiAgICByZWY6IHJlZixcbiAgICBwcm9wczogcHJvcHMsXG4gICAgLy8gUmVjb3JkIHRoZSBjb21wb25lbnQgcmVzcG9uc2libGUgZm9yIGNyZWF0aW5nIHRoaXMgZWxlbWVudC5cbiAgICBfb3duZXI6IG93bmVyXG4gIH07XG5cbiAge1xuICAgIC8vIFRoZSB2YWxpZGF0aW9uIGZsYWcgaXMgY3VycmVudGx5IG11dGF0aXZlLiBXZSBwdXQgaXQgb25cbiAgICAvLyBhbiBleHRlcm5hbCBiYWNraW5nIHN0b3JlIHNvIHRoYXQgd2UgY2FuIGZyZWV6ZSB0aGUgd2hvbGUgb2JqZWN0LlxuICAgIC8vIFRoaXMgY2FuIGJlIHJlcGxhY2VkIHdpdGggYSBXZWFrTWFwIG9uY2UgdGhleSBhcmUgaW1wbGVtZW50ZWQgaW5cbiAgICAvLyBjb21tb25seSB1c2VkIGRldmVsb3BtZW50IGVudmlyb25tZW50cy5cbiAgICBlbGVtZW50Ll9zdG9yZSA9IHt9OyAvLyBUbyBtYWtlIGNvbXBhcmluZyBSZWFjdEVsZW1lbnRzIGVhc2llciBmb3IgdGVzdGluZyBwdXJwb3Nlcywgd2UgbWFrZVxuICAgIC8vIHRoZSB2YWxpZGF0aW9uIGZsYWcgbm9uLWVudW1lcmFibGUgKHdoZXJlIHBvc3NpYmxlLCB3aGljaCBzaG91bGRcbiAgICAvLyBpbmNsdWRlIGV2ZXJ5IGVudmlyb25tZW50IHdlIHJ1biB0ZXN0cyBpbiksIHNvIHRoZSB0ZXN0IGZyYW1ld29ya1xuICAgIC8vIGlnbm9yZXMgaXQuXG5cbiAgICBPYmplY3QuZGVmaW5lUHJvcGVydHkoZWxlbWVudC5fc3RvcmUsICd2YWxpZGF0ZWQnLCB7XG4gICAgICBjb25maWd1cmFibGU6IGZhbHNlLFxuICAgICAgZW51bWVyYWJsZTogZmFsc2UsXG4gICAgICB3cml0YWJsZTogdHJ1ZSxcbiAgICAgIHZhbHVlOiBmYWxzZVxuICAgIH0pOyAvLyBzZWxmIGFuZCBzb3VyY2UgYXJlIERFViBvbmx5IHByb3BlcnRpZXMuXG5cbiAgICBPYmplY3QuZGVmaW5lUHJvcGVydHkoZWxlbWVudCwgJ19zZWxmJywge1xuICAgICAgY29uZmlndXJhYmxlOiBmYWxzZSxcbiAgICAgIGVudW1lcmFibGU6IGZhbHNlLFxuICAgICAgd3JpdGFibGU6IGZhbHNlLFxuICAgICAgdmFsdWU6IHNlbGZcbiAgICB9KTsgLy8gVHdvIGVsZW1lbnRzIGNyZWF0ZWQgaW4gdHdvIGRpZmZlcmVudCBwbGFjZXMgc2hvdWxkIGJlIGNvbnNpZGVyZWRcbiAgICAvLyBlcXVhbCBmb3IgdGVzdGluZyBwdXJwb3NlcyBhbmQgdGhlcmVmb3JlIHdlIGhpZGUgaXQgZnJvbSBlbnVtZXJhdGlvbi5cblxuICAgIE9iamVjdC5kZWZpbmVQcm9wZXJ0eShlbGVtZW50LCAnX3NvdXJjZScsIHtcbiAgICAgIGNvbmZpZ3VyYWJsZTogZmFsc2UsXG4gICAgICBlbnVtZXJhYmxlOiBmYWxzZSxcbiAgICAgIHdyaXRhYmxlOiBmYWxzZSxcbiAgICAgIHZhbHVlOiBzb3VyY2VcbiAgICB9KTtcblxuICAgIGlmIChPYmplY3QuZnJlZXplKSB7XG4gICAgICBPYmplY3QuZnJlZXplKGVsZW1lbnQucHJvcHMpO1xuICAgICAgT2JqZWN0LmZyZWV6ZShlbGVtZW50KTtcbiAgICB9XG4gIH1cblxuICByZXR1cm4gZWxlbWVudDtcbn07XG4vKipcbiAqIGh0dHBzOi8vZ2l0aHViLmNvbS9yZWFjdGpzL3JmY3MvcHVsbC8xMDdcbiAqIEBwYXJhbSB7Kn0gdHlwZVxuICogQHBhcmFtIHtvYmplY3R9IHByb3BzXG4gKiBAcGFyYW0ge3N0cmluZ30ga2V5XG4gKi9cblxuZnVuY3Rpb24ganN4REVWKHR5cGUsIGNvbmZpZywgbWF5YmVLZXksIHNvdXJjZSwgc2VsZikge1xuICB7XG4gICAgdmFyIHByb3BOYW1lOyAvLyBSZXNlcnZlZCBuYW1lcyBhcmUgZXh0cmFjdGVkXG5cbiAgICB2YXIgcHJvcHMgPSB7fTtcbiAgICB2YXIga2V5ID0gbnVsbDtcbiAgICB2YXIgcmVmID0gbnVsbDsgLy8gQ3VycmVudGx5LCBrZXkgY2FuIGJlIHNwcmVhZCBpbiBhcyBhIHByb3AuIFRoaXMgY2F1c2VzIGEgcG90ZW50aWFsXG4gICAgLy8gaXNzdWUgaWYga2V5IGlzIGFsc28gZXhwbGljaXRseSBkZWNsYXJlZCAoaWUuIDxkaXYgey4uLnByb3BzfSBrZXk9XCJIaVwiIC8+XG4gICAgLy8gb3IgPGRpdiBrZXk9XCJIaVwiIHsuLi5wcm9wc30gLz4gKS4gV2Ugd2FudCB0byBkZXByZWNhdGUga2V5IHNwcmVhZCxcbiAgICAvLyBidXQgYXMgYW4gaW50ZXJtZWRpYXJ5IHN0ZXAsIHdlIHdpbGwgdXNlIGpzeERFViBmb3IgZXZlcnl0aGluZyBleGNlcHRcbiAgICAvLyA8ZGl2IHsuLi5wcm9wc30ga2V5PVwiSGlcIiAvPiwgYmVjYXVzZSB3ZSBhcmVuJ3QgY3VycmVudGx5IGFibGUgdG8gdGVsbCBpZlxuICAgIC8vIGtleSBpcyBleHBsaWNpdGx5IGRlY2xhcmVkIHRvIGJlIHVuZGVmaW5lZCBvciBub3QuXG5cbiAgICBpZiAobWF5YmVLZXkgIT09IHVuZGVmaW5lZCkge1xuICAgICAge1xuICAgICAgICBjaGVja0tleVN0cmluZ0NvZXJjaW9uKG1heWJlS2V5KTtcbiAgICAgIH1cblxuICAgICAga2V5ID0gJycgKyBtYXliZUtleTtcbiAgICB9XG5cbiAgICBpZiAoaGFzVmFsaWRLZXkoY29uZmlnKSkge1xuICAgICAge1xuICAgICAgICBjaGVja0tleVN0cmluZ0NvZXJjaW9uKGNvbmZpZy5rZXkpO1xuICAgICAgfVxuXG4gICAgICBrZXkgPSAnJyArIGNvbmZpZy5rZXk7XG4gICAgfVxuXG4gICAgaWYgKGhhc1ZhbGlkUmVmKGNvbmZpZykpIHtcbiAgICAgIHJlZiA9IGNvbmZpZy5yZWY7XG4gICAgICB3YXJuSWZTdHJpbmdSZWZDYW5ub3RCZUF1dG9Db252ZXJ0ZWQoY29uZmlnLCBzZWxmKTtcbiAgICB9IC8vIFJlbWFpbmluZyBwcm9wZXJ0aWVzIGFyZSBhZGRlZCB0byBhIG5ldyBwcm9wcyBvYmplY3RcblxuXG4gICAgZm9yIChwcm9wTmFtZSBpbiBjb25maWcpIHtcbiAgICAgIGlmIChoYXNPd25Qcm9wZXJ0eS5jYWxsKGNvbmZpZywgcHJvcE5hbWUpICYmICFSRVNFUlZFRF9QUk9QUy5oYXNPd25Qcm9wZXJ0eShwcm9wTmFtZSkpIHtcbiAgICAgICAgcHJvcHNbcHJvcE5hbWVdID0gY29uZmlnW3Byb3BOYW1lXTtcbiAgICAgIH1cbiAgICB9IC8vIFJlc29sdmUgZGVmYXVsdCBwcm9wc1xuXG5cbiAgICBpZiAodHlwZSAmJiB0eXBlLmRlZmF1bHRQcm9wcykge1xuICAgICAgdmFyIGRlZmF1bHRQcm9wcyA9IHR5cGUuZGVmYXVsdFByb3BzO1xuXG4gICAgICBmb3IgKHByb3BOYW1lIGluIGRlZmF1bHRQcm9wcykge1xuICAgICAgICBpZiAocHJvcHNbcHJvcE5hbWVdID09PSB1bmRlZmluZWQpIHtcbiAgICAgICAgICBwcm9wc1twcm9wTmFtZV0gPSBkZWZhdWx0UHJvcHNbcHJvcE5hbWVdO1xuICAgICAgICB9XG4gICAgICB9XG4gICAgfVxuXG4gICAgaWYgKGtleSB8fCByZWYpIHtcbiAgICAgIHZhciBkaXNwbGF5TmFtZSA9IHR5cGVvZiB0eXBlID09PSAnZnVuY3Rpb24nID8gdHlwZS5kaXNwbGF5TmFtZSB8fCB0eXBlLm5hbWUgfHwgJ1Vua25vd24nIDogdHlwZTtcblxuICAgICAgaWYgKGtleSkge1xuICAgICAgICBkZWZpbmVLZXlQcm9wV2FybmluZ0dldHRlcihwcm9wcywgZGlzcGxheU5hbWUpO1xuICAgICAgfVxuXG4gICAgICBpZiAocmVmKSB7XG4gICAgICAgIGRlZmluZVJlZlByb3BXYXJuaW5nR2V0dGVyKHByb3BzLCBkaXNwbGF5TmFtZSk7XG4gICAgICB9XG4gICAgfVxuXG4gICAgcmV0dXJuIFJlYWN0RWxlbWVudCh0eXBlLCBrZXksIHJlZiwgc2VsZiwgc291cmNlLCBSZWFjdEN1cnJlbnRPd25lci5jdXJyZW50LCBwcm9wcyk7XG4gIH1cbn1cblxudmFyIFJlYWN0Q3VycmVudE93bmVyJDEgPSBSZWFjdFNoYXJlZEludGVybmFscy5SZWFjdEN1cnJlbnRPd25lcjtcbnZhciBSZWFjdERlYnVnQ3VycmVudEZyYW1lJDEgPSBSZWFjdFNoYXJlZEludGVybmFscy5SZWFjdERlYnVnQ3VycmVudEZyYW1lO1xuXG5mdW5jdGlvbiBzZXRDdXJyZW50bHlWYWxpZGF0aW5nRWxlbWVudCQxKGVsZW1lbnQpIHtcbiAge1xuICAgIGlmIChlbGVtZW50KSB7XG4gICAgICB2YXIgb3duZXIgPSBlbGVtZW50Ll9vd25lcjtcbiAgICAgIHZhciBzdGFjayA9IGRlc2NyaWJlVW5rbm93bkVsZW1lbnRUeXBlRnJhbWVJbkRFVihlbGVtZW50LnR5cGUsIGVsZW1lbnQuX3NvdXJjZSwgb3duZXIgPyBvd25lci50eXBlIDogbnVsbCk7XG4gICAgICBSZWFjdERlYnVnQ3VycmVudEZyYW1lJDEuc2V0RXh0cmFTdGFja0ZyYW1lKHN0YWNrKTtcbiAgICB9IGVsc2Uge1xuICAgICAgUmVhY3REZWJ1Z0N1cnJlbnRGcmFtZSQxLnNldEV4dHJhU3RhY2tGcmFtZShudWxsKTtcbiAgICB9XG4gIH1cbn1cblxudmFyIHByb3BUeXBlc01pc3NwZWxsV2FybmluZ1Nob3duO1xuXG57XG4gIHByb3BUeXBlc01pc3NwZWxsV2FybmluZ1Nob3duID0gZmFsc2U7XG59XG4vKipcbiAqIFZlcmlmaWVzIHRoZSBvYmplY3QgaXMgYSBSZWFjdEVsZW1lbnQuXG4gKiBTZWUgaHR0cHM6Ly9yZWFjdGpzLm9yZy9kb2NzL3JlYWN0LWFwaS5odG1sI2lzdmFsaWRlbGVtZW50XG4gKiBAcGFyYW0gez9vYmplY3R9IG9iamVjdFxuICogQHJldHVybiB7Ym9vbGVhbn0gVHJ1ZSBpZiBgb2JqZWN0YCBpcyBhIFJlYWN0RWxlbWVudC5cbiAqIEBmaW5hbFxuICovXG5cblxuZnVuY3Rpb24gaXNWYWxpZEVsZW1lbnQob2JqZWN0KSB7XG4gIHtcbiAgICByZXR1cm4gdHlwZW9mIG9iamVjdCA9PT0gJ29iamVjdCcgJiYgb2JqZWN0ICE9PSBudWxsICYmIG9iamVjdC4kJHR5cGVvZiA9PT0gUkVBQ1RfRUxFTUVOVF9UWVBFO1xuICB9XG59XG5cbmZ1bmN0aW9uIGdldERlY2xhcmF0aW9uRXJyb3JBZGRlbmR1bSgpIHtcbiAge1xuICAgIGlmIChSZWFjdEN1cnJlbnRPd25lciQxLmN1cnJlbnQpIHtcbiAgICAgIHZhciBuYW1lID0gZ2V0Q29tcG9uZW50TmFtZUZyb21UeXBlKFJlYWN0Q3VycmVudE93bmVyJDEuY3VycmVudC50eXBlKTtcblxuICAgICAgaWYgKG5hbWUpIHtcbiAgICAgICAgcmV0dXJuICdcXG5cXG5DaGVjayB0aGUgcmVuZGVyIG1ldGhvZCBvZiBgJyArIG5hbWUgKyAnYC4nO1xuICAgICAgfVxuICAgIH1cblxuICAgIHJldHVybiAnJztcbiAgfVxufVxuXG5mdW5jdGlvbiBnZXRTb3VyY2VJbmZvRXJyb3JBZGRlbmR1bShzb3VyY2UpIHtcbiAge1xuICAgIGlmIChzb3VyY2UgIT09IHVuZGVmaW5lZCkge1xuICAgICAgdmFyIGZpbGVOYW1lID0gc291cmNlLmZpbGVOYW1lLnJlcGxhY2UoL14uKltcXFxcXFwvXS8sICcnKTtcbiAgICAgIHZhciBsaW5lTnVtYmVyID0gc291cmNlLmxpbmVOdW1iZXI7XG4gICAgICByZXR1cm4gJ1xcblxcbkNoZWNrIHlvdXIgY29kZSBhdCAnICsgZmlsZU5hbWUgKyAnOicgKyBsaW5lTnVtYmVyICsgJy4nO1xuICAgIH1cblxuICAgIHJldHVybiAnJztcbiAgfVxufVxuLyoqXG4gKiBXYXJuIGlmIHRoZXJlJ3Mgbm8ga2V5IGV4cGxpY2l0bHkgc2V0IG9uIGR5bmFtaWMgYXJyYXlzIG9mIGNoaWxkcmVuIG9yXG4gKiBvYmplY3Qga2V5cyBhcmUgbm90IHZhbGlkLiBUaGlzIGFsbG93cyB1cyB0byBrZWVwIHRyYWNrIG9mIGNoaWxkcmVuIGJldHdlZW5cbiAqIHVwZGF0ZXMuXG4gKi9cblxuXG52YXIgb3duZXJIYXNLZXlVc2VXYXJuaW5nID0ge307XG5cbmZ1bmN0aW9uIGdldEN1cnJlbnRDb21wb25lbnRFcnJvckluZm8ocGFyZW50VHlwZSkge1xuICB7XG4gICAgdmFyIGluZm8gPSBnZXREZWNsYXJhdGlvbkVycm9yQWRkZW5kdW0oKTtcblxuICAgIGlmICghaW5mbykge1xuICAgICAgdmFyIHBhcmVudE5hbWUgPSB0eXBlb2YgcGFyZW50VHlwZSA9PT0gJ3N0cmluZycgPyBwYXJlbnRUeXBlIDogcGFyZW50VHlwZS5kaXNwbGF5TmFtZSB8fCBwYXJlbnRUeXBlLm5hbWU7XG5cbiAgICAgIGlmIChwYXJlbnROYW1lKSB7XG4gICAgICAgIGluZm8gPSBcIlxcblxcbkNoZWNrIHRoZSB0b3AtbGV2ZWwgcmVuZGVyIGNhbGwgdXNpbmcgPFwiICsgcGFyZW50TmFtZSArIFwiPi5cIjtcbiAgICAgIH1cbiAgICB9XG5cbiAgICByZXR1cm4gaW5mbztcbiAgfVxufVxuLyoqXG4gKiBXYXJuIGlmIHRoZSBlbGVtZW50IGRvZXNuJ3QgaGF2ZSBhbiBleHBsaWNpdCBrZXkgYXNzaWduZWQgdG8gaXQuXG4gKiBUaGlzIGVsZW1lbnQgaXMgaW4gYW4gYXJyYXkuIFRoZSBhcnJheSBjb3VsZCBncm93IGFuZCBzaHJpbmsgb3IgYmVcbiAqIHJlb3JkZXJlZC4gQWxsIGNoaWxkcmVuIHRoYXQgaGF2ZW4ndCBhbHJlYWR5IGJlZW4gdmFsaWRhdGVkIGFyZSByZXF1aXJlZCB0b1xuICogaGF2ZSBhIFwia2V5XCIgcHJvcGVydHkgYXNzaWduZWQgdG8gaXQuIEVycm9yIHN0YXR1c2VzIGFyZSBjYWNoZWQgc28gYSB3YXJuaW5nXG4gKiB3aWxsIG9ubHkgYmUgc2hvd24gb25jZS5cbiAqXG4gKiBAaW50ZXJuYWxcbiAqIEBwYXJhbSB7UmVhY3RFbGVtZW50fSBlbGVtZW50IEVsZW1lbnQgdGhhdCByZXF1aXJlcyBhIGtleS5cbiAqIEBwYXJhbSB7Kn0gcGFyZW50VHlwZSBlbGVtZW50J3MgcGFyZW50J3MgdHlwZS5cbiAqL1xuXG5cbmZ1bmN0aW9uIHZhbGlkYXRlRXhwbGljaXRLZXkoZWxlbWVudCwgcGFyZW50VHlwZSkge1xuICB7XG4gICAgaWYgKCFlbGVtZW50Ll9zdG9yZSB8fCBlbGVtZW50Ll9zdG9yZS52YWxpZGF0ZWQgfHwgZWxlbWVudC5rZXkgIT0gbnVsbCkge1xuICAgICAgcmV0dXJuO1xuICAgIH1cblxuICAgIGVsZW1lbnQuX3N0b3JlLnZhbGlkYXRlZCA9IHRydWU7XG4gICAgdmFyIGN1cnJlbnRDb21wb25lbnRFcnJvckluZm8gPSBnZXRDdXJyZW50Q29tcG9uZW50RXJyb3JJbmZvKHBhcmVudFR5cGUpO1xuXG4gICAgaWYgKG93bmVySGFzS2V5VXNlV2FybmluZ1tjdXJyZW50Q29tcG9uZW50RXJyb3JJbmZvXSkge1xuICAgICAgcmV0dXJuO1xuICAgIH1cblxuICAgIG93bmVySGFzS2V5VXNlV2FybmluZ1tjdXJyZW50Q29tcG9uZW50RXJyb3JJbmZvXSA9IHRydWU7IC8vIFVzdWFsbHkgdGhlIGN1cnJlbnQgb3duZXIgaXMgdGhlIG9mZmVuZGVyLCBidXQgaWYgaXQgYWNjZXB0cyBjaGlsZHJlbiBhcyBhXG4gICAgLy8gcHJvcGVydHksIGl0IG1heSBiZSB0aGUgY3JlYXRvciBvZiB0aGUgY2hpbGQgdGhhdCdzIHJlc3BvbnNpYmxlIGZvclxuICAgIC8vIGFzc2lnbmluZyBpdCBhIGtleS5cblxuICAgIHZhciBjaGlsZE93bmVyID0gJyc7XG5cbiAgICBpZiAoZWxlbWVudCAmJiBlbGVtZW50Ll9vd25lciAmJiBlbGVtZW50Ll9vd25lciAhPT0gUmVhY3RDdXJyZW50T3duZXIkMS5jdXJyZW50KSB7XG4gICAgICAvLyBHaXZlIHRoZSBjb21wb25lbnQgdGhhdCBvcmlnaW5hbGx5IGNyZWF0ZWQgdGhpcyBjaGlsZC5cbiAgICAgIGNoaWxkT3duZXIgPSBcIiBJdCB3YXMgcGFzc2VkIGEgY2hpbGQgZnJvbSBcIiArIGdldENvbXBvbmVudE5hbWVGcm9tVHlwZShlbGVtZW50Ll9vd25lci50eXBlKSArIFwiLlwiO1xuICAgIH1cblxuICAgIHNldEN1cnJlbnRseVZhbGlkYXRpbmdFbGVtZW50JDEoZWxlbWVudCk7XG5cbiAgICBlcnJvcignRWFjaCBjaGlsZCBpbiBhIGxpc3Qgc2hvdWxkIGhhdmUgYSB1bmlxdWUgXCJrZXlcIiBwcm9wLicgKyAnJXMlcyBTZWUgaHR0cHM6Ly9yZWFjdGpzLm9yZy9saW5rL3dhcm5pbmcta2V5cyBmb3IgbW9yZSBpbmZvcm1hdGlvbi4nLCBjdXJyZW50Q29tcG9uZW50RXJyb3JJbmZvLCBjaGlsZE93bmVyKTtcblxuICAgIHNldEN1cnJlbnRseVZhbGlkYXRpbmdFbGVtZW50JDEobnVsbCk7XG4gIH1cbn1cbi8qKlxuICogRW5zdXJlIHRoYXQgZXZlcnkgZWxlbWVudCBlaXRoZXIgaXMgcGFzc2VkIGluIGEgc3RhdGljIGxvY2F0aW9uLCBpbiBhblxuICogYXJyYXkgd2l0aCBhbiBleHBsaWNpdCBrZXlzIHByb3BlcnR5IGRlZmluZWQsIG9yIGluIGFuIG9iamVjdCBsaXRlcmFsXG4gKiB3aXRoIHZhbGlkIGtleSBwcm9wZXJ0eS5cbiAqXG4gKiBAaW50ZXJuYWxcbiAqIEBwYXJhbSB7UmVhY3ROb2RlfSBub2RlIFN0YXRpY2FsbHkgcGFzc2VkIGNoaWxkIG9mIGFueSB0eXBlLlxuICogQHBhcmFtIHsqfSBwYXJlbnRUeXBlIG5vZGUncyBwYXJlbnQncyB0eXBlLlxuICovXG5cblxuZnVuY3Rpb24gdmFsaWRhdGVDaGlsZEtleXMobm9kZSwgcGFyZW50VHlwZSkge1xuICB7XG4gICAgaWYgKHR5cGVvZiBub2RlICE9PSAnb2JqZWN0Jykge1xuICAgICAgcmV0dXJuO1xuICAgIH1cblxuICAgIGlmIChpc0FycmF5KG5vZGUpKSB7XG4gICAgICBmb3IgKHZhciBpID0gMDsgaSA8IG5vZGUubGVuZ3RoOyBpKyspIHtcbiAgICAgICAgdmFyIGNoaWxkID0gbm9kZVtpXTtcblxuICAgICAgICBpZiAoaXNWYWxpZEVsZW1lbnQoY2hpbGQpKSB7XG4gICAgICAgICAgdmFsaWRhdGVFeHBsaWNpdEtleShjaGlsZCwgcGFyZW50VHlwZSk7XG4gICAgICAgIH1cbiAgICAgIH1cbiAgICB9IGVsc2UgaWYgKGlzVmFsaWRFbGVtZW50KG5vZGUpKSB7XG4gICAgICAvLyBUaGlzIGVsZW1lbnQgd2FzIHBhc3NlZCBpbiBhIHZhbGlkIGxvY2F0aW9uLlxuICAgICAgaWYgKG5vZGUuX3N0b3JlKSB7XG4gICAgICAgIG5vZGUuX3N0b3JlLnZhbGlkYXRlZCA9IHRydWU7XG4gICAgICB9XG4gICAgfSBlbHNlIGlmIChub2RlKSB7XG4gICAgICB2YXIgaXRlcmF0b3JGbiA9IGdldEl0ZXJhdG9yRm4obm9kZSk7XG5cbiAgICAgIGlmICh0eXBlb2YgaXRlcmF0b3JGbiA9PT0gJ2Z1bmN0aW9uJykge1xuICAgICAgICAvLyBFbnRyeSBpdGVyYXRvcnMgdXNlZCB0byBwcm92aWRlIGltcGxpY2l0IGtleXMsXG4gICAgICAgIC8vIGJ1dCBub3cgd2UgcHJpbnQgYSBzZXBhcmF0ZSB3YXJuaW5nIGZvciB0aGVtIGxhdGVyLlxuICAgICAgICBpZiAoaXRlcmF0b3JGbiAhPT0gbm9kZS5lbnRyaWVzKSB7XG4gICAgICAgICAgdmFyIGl0ZXJhdG9yID0gaXRlcmF0b3JGbi5jYWxsKG5vZGUpO1xuICAgICAgICAgIHZhciBzdGVwO1xuXG4gICAgICAgICAgd2hpbGUgKCEoc3RlcCA9IGl0ZXJhdG9yLm5leHQoKSkuZG9uZSkge1xuICAgICAgICAgICAgaWYgKGlzVmFsaWRFbGVtZW50KHN0ZXAudmFsdWUpKSB7XG4gICAgICAgICAgICAgIHZhbGlkYXRlRXhwbGljaXRLZXkoc3RlcC52YWx1ZSwgcGFyZW50VHlwZSk7XG4gICAgICAgICAgICB9XG4gICAgICAgICAgfVxuICAgICAgICB9XG4gICAgICB9XG4gICAgfVxuICB9XG59XG4vKipcbiAqIEdpdmVuIGFuIGVsZW1lbnQsIHZhbGlkYXRlIHRoYXQgaXRzIHByb3BzIGZvbGxvdyB0aGUgcHJvcFR5cGVzIGRlZmluaXRpb24sXG4gKiBwcm92aWRlZCBieSB0aGUgdHlwZS5cbiAqXG4gKiBAcGFyYW0ge1JlYWN0RWxlbWVudH0gZWxlbWVudFxuICovXG5cblxuZnVuY3Rpb24gdmFsaWRhdGVQcm9wVHlwZXMoZWxlbWVudCkge1xuICB7XG4gICAgdmFyIHR5cGUgPSBlbGVtZW50LnR5cGU7XG5cbiAgICBpZiAodHlwZSA9PT0gbnVsbCB8fCB0eXBlID09PSB1bmRlZmluZWQgfHwgdHlwZW9mIHR5cGUgPT09ICdzdHJpbmcnKSB7XG4gICAgICByZXR1cm47XG4gICAgfVxuXG4gICAgdmFyIHByb3BUeXBlcztcblxuICAgIGlmICh0eXBlb2YgdHlwZSA9PT0gJ2Z1bmN0aW9uJykge1xuICAgICAgcHJvcFR5cGVzID0gdHlwZS5wcm9wVHlwZXM7XG4gICAgfSBlbHNlIGlmICh0eXBlb2YgdHlwZSA9PT0gJ29iamVjdCcgJiYgKHR5cGUuJCR0eXBlb2YgPT09IFJFQUNUX0ZPUldBUkRfUkVGX1RZUEUgfHwgLy8gTm90ZTogTWVtbyBvbmx5IGNoZWNrcyBvdXRlciBwcm9wcyBoZXJlLlxuICAgIC8vIElubmVyIHByb3BzIGFyZSBjaGVja2VkIGluIHRoZSByZWNvbmNpbGVyLlxuICAgIHR5cGUuJCR0eXBlb2YgPT09IFJFQUNUX01FTU9fVFlQRSkpIHtcbiAgICAgIHByb3BUeXBlcyA9IHR5cGUucHJvcFR5cGVzO1xuICAgIH0gZWxzZSB7XG4gICAgICByZXR1cm47XG4gICAgfVxuXG4gICAgaWYgKHByb3BUeXBlcykge1xuICAgICAgLy8gSW50ZW50aW9uYWxseSBpbnNpZGUgdG8gYXZvaWQgdHJpZ2dlcmluZyBsYXp5IGluaXRpYWxpemVyczpcbiAgICAgIHZhciBuYW1lID0gZ2V0Q29tcG9uZW50TmFtZUZyb21UeXBlKHR5cGUpO1xuICAgICAgY2hlY2tQcm9wVHlwZXMocHJvcFR5cGVzLCBlbGVtZW50LnByb3BzLCAncHJvcCcsIG5hbWUsIGVsZW1lbnQpO1xuICAgIH0gZWxzZSBpZiAodHlwZS5Qcm9wVHlwZXMgIT09IHVuZGVmaW5lZCAmJiAhcHJvcFR5cGVzTWlzc3BlbGxXYXJuaW5nU2hvd24pIHtcbiAgICAgIHByb3BUeXBlc01pc3NwZWxsV2FybmluZ1Nob3duID0gdHJ1ZTsgLy8gSW50ZW50aW9uYWxseSBpbnNpZGUgdG8gYXZvaWQgdHJpZ2dlcmluZyBsYXp5IGluaXRpYWxpemVyczpcblxuICAgICAgdmFyIF9uYW1lID0gZ2V0Q29tcG9uZW50TmFtZUZyb21UeXBlKHR5cGUpO1xuXG4gICAgICBlcnJvcignQ29tcG9uZW50ICVzIGRlY2xhcmVkIGBQcm9wVHlwZXNgIGluc3RlYWQgb2YgYHByb3BUeXBlc2AuIERpZCB5b3UgbWlzc3BlbGwgdGhlIHByb3BlcnR5IGFzc2lnbm1lbnQ/JywgX25hbWUgfHwgJ1Vua25vd24nKTtcbiAgICB9XG5cbiAgICBpZiAodHlwZW9mIHR5cGUuZ2V0RGVmYXVsdFByb3BzID09PSAnZnVuY3Rpb24nICYmICF0eXBlLmdldERlZmF1bHRQcm9wcy5pc1JlYWN0Q2xhc3NBcHByb3ZlZCkge1xuICAgICAgZXJyb3IoJ2dldERlZmF1bHRQcm9wcyBpcyBvbmx5IHVzZWQgb24gY2xhc3NpYyBSZWFjdC5jcmVhdGVDbGFzcyAnICsgJ2RlZmluaXRpb25zLiBVc2UgYSBzdGF0aWMgcHJvcGVydHkgbmFtZWQgYGRlZmF1bHRQcm9wc2AgaW5zdGVhZC4nKTtcbiAgICB9XG4gIH1cbn1cbi8qKlxuICogR2l2ZW4gYSBmcmFnbWVudCwgdmFsaWRhdGUgdGhhdCBpdCBjYW4gb25seSBiZSBwcm92aWRlZCB3aXRoIGZyYWdtZW50IHByb3BzXG4gKiBAcGFyYW0ge1JlYWN0RWxlbWVudH0gZnJhZ21lbnRcbiAqL1xuXG5cbmZ1bmN0aW9uIHZhbGlkYXRlRnJhZ21lbnRQcm9wcyhmcmFnbWVudCkge1xuICB7XG4gICAgdmFyIGtleXMgPSBPYmplY3Qua2V5cyhmcmFnbWVudC5wcm9wcyk7XG5cbiAgICBmb3IgKHZhciBpID0gMDsgaSA8IGtleXMubGVuZ3RoOyBpKyspIHtcbiAgICAgIHZhciBrZXkgPSBrZXlzW2ldO1xuXG4gICAgICBpZiAoa2V5ICE9PSAnY2hpbGRyZW4nICYmIGtleSAhPT0gJ2tleScpIHtcbiAgICAgICAgc2V0Q3VycmVudGx5VmFsaWRhdGluZ0VsZW1lbnQkMShmcmFnbWVudCk7XG5cbiAgICAgICAgZXJyb3IoJ0ludmFsaWQgcHJvcCBgJXNgIHN1cHBsaWVkIHRvIGBSZWFjdC5GcmFnbWVudGAuICcgKyAnUmVhY3QuRnJhZ21lbnQgY2FuIG9ubHkgaGF2ZSBga2V5YCBhbmQgYGNoaWxkcmVuYCBwcm9wcy4nLCBrZXkpO1xuXG4gICAgICAgIHNldEN1cnJlbnRseVZhbGlkYXRpbmdFbGVtZW50JDEobnVsbCk7XG4gICAgICAgIGJyZWFrO1xuICAgICAgfVxuICAgIH1cblxuICAgIGlmIChmcmFnbWVudC5yZWYgIT09IG51bGwpIHtcbiAgICAgIHNldEN1cnJlbnRseVZhbGlkYXRpbmdFbGVtZW50JDEoZnJhZ21lbnQpO1xuXG4gICAgICBlcnJvcignSW52YWxpZCBhdHRyaWJ1dGUgYHJlZmAgc3VwcGxpZWQgdG8gYFJlYWN0LkZyYWdtZW50YC4nKTtcblxuICAgICAgc2V0Q3VycmVudGx5VmFsaWRhdGluZ0VsZW1lbnQkMShudWxsKTtcbiAgICB9XG4gIH1cbn1cblxudmFyIGRpZFdhcm5BYm91dEtleVNwcmVhZCA9IHt9O1xuZnVuY3Rpb24ganN4V2l0aFZhbGlkYXRpb24odHlwZSwgcHJvcHMsIGtleSwgaXNTdGF0aWNDaGlsZHJlbiwgc291cmNlLCBzZWxmKSB7XG4gIHtcbiAgICB2YXIgdmFsaWRUeXBlID0gaXNWYWxpZEVsZW1lbnRUeXBlKHR5cGUpOyAvLyBXZSB3YXJuIGluIHRoaXMgY2FzZSBidXQgZG9uJ3QgdGhyb3cuIFdlIGV4cGVjdCB0aGUgZWxlbWVudCBjcmVhdGlvbiB0b1xuICAgIC8vIHN1Y2NlZWQgYW5kIHRoZXJlIHdpbGwgbGlrZWx5IGJlIGVycm9ycyBpbiByZW5kZXIuXG5cbiAgICBpZiAoIXZhbGlkVHlwZSkge1xuICAgICAgdmFyIGluZm8gPSAnJztcblxuICAgICAgaWYgKHR5cGUgPT09IHVuZGVmaW5lZCB8fCB0eXBlb2YgdHlwZSA9PT0gJ29iamVjdCcgJiYgdHlwZSAhPT0gbnVsbCAmJiBPYmplY3Qua2V5cyh0eXBlKS5sZW5ndGggPT09IDApIHtcbiAgICAgICAgaW5mbyArPSAnIFlvdSBsaWtlbHkgZm9yZ290IHRvIGV4cG9ydCB5b3VyIGNvbXBvbmVudCBmcm9tIHRoZSBmaWxlICcgKyBcIml0J3MgZGVmaW5lZCBpbiwgb3IgeW91IG1pZ2h0IGhhdmUgbWl4ZWQgdXAgZGVmYXVsdCBhbmQgbmFtZWQgaW1wb3J0cy5cIjtcbiAgICAgIH1cblxuICAgICAgdmFyIHNvdXJjZUluZm8gPSBnZXRTb3VyY2VJbmZvRXJyb3JBZGRlbmR1bShzb3VyY2UpO1xuXG4gICAgICBpZiAoc291cmNlSW5mbykge1xuICAgICAgICBpbmZvICs9IHNvdXJjZUluZm87XG4gICAgICB9IGVsc2Uge1xuICAgICAgICBpbmZvICs9IGdldERlY2xhcmF0aW9uRXJyb3JBZGRlbmR1bSgpO1xuICAgICAgfVxuXG4gICAgICB2YXIgdHlwZVN0cmluZztcblxuICAgICAgaWYgKHR5cGUgPT09IG51bGwpIHtcbiAgICAgICAgdHlwZVN0cmluZyA9ICdudWxsJztcbiAgICAgIH0gZWxzZSBpZiAoaXNBcnJheSh0eXBlKSkge1xuICAgICAgICB0eXBlU3RyaW5nID0gJ2FycmF5JztcbiAgICAgIH0gZWxzZSBpZiAodHlwZSAhPT0gdW5kZWZpbmVkICYmIHR5cGUuJCR0eXBlb2YgPT09IFJFQUNUX0VMRU1FTlRfVFlQRSkge1xuICAgICAgICB0eXBlU3RyaW5nID0gXCI8XCIgKyAoZ2V0Q29tcG9uZW50TmFtZUZyb21UeXBlKHR5cGUudHlwZSkgfHwgJ1Vua25vd24nKSArIFwiIC8+XCI7XG4gICAgICAgIGluZm8gPSAnIERpZCB5b3UgYWNjaWRlbnRhbGx5IGV4cG9ydCBhIEpTWCBsaXRlcmFsIGluc3RlYWQgb2YgYSBjb21wb25lbnQ/JztcbiAgICAgIH0gZWxzZSB7XG4gICAgICAgIHR5cGVTdHJpbmcgPSB0eXBlb2YgdHlwZTtcbiAgICAgIH1cblxuICAgICAgZXJyb3IoJ1JlYWN0LmpzeDogdHlwZSBpcyBpbnZhbGlkIC0tIGV4cGVjdGVkIGEgc3RyaW5nIChmb3IgJyArICdidWlsdC1pbiBjb21wb25lbnRzKSBvciBhIGNsYXNzL2Z1bmN0aW9uIChmb3IgY29tcG9zaXRlICcgKyAnY29tcG9uZW50cykgYnV0IGdvdDogJXMuJXMnLCB0eXBlU3RyaW5nLCBpbmZvKTtcbiAgICB9XG5cbiAgICB2YXIgZWxlbWVudCA9IGpzeERFVih0eXBlLCBwcm9wcywga2V5LCBzb3VyY2UsIHNlbGYpOyAvLyBUaGUgcmVzdWx0IGNhbiBiZSBudWxsaXNoIGlmIGEgbW9jayBvciBhIGN1c3RvbSBmdW5jdGlvbiBpcyB1c2VkLlxuICAgIC8vIFRPRE86IERyb3AgdGhpcyB3aGVuIHRoZXNlIGFyZSBubyBsb25nZXIgYWxsb3dlZCBhcyB0aGUgdHlwZSBhcmd1bWVudC5cblxuICAgIGlmIChlbGVtZW50ID09IG51bGwpIHtcbiAgICAgIHJldHVybiBlbGVtZW50O1xuICAgIH0gLy8gU2tpcCBrZXkgd2FybmluZyBpZiB0aGUgdHlwZSBpc24ndCB2YWxpZCBzaW5jZSBvdXIga2V5IHZhbGlkYXRpb24gbG9naWNcbiAgICAvLyBkb2Vzbid0IGV4cGVjdCBhIG5vbi1zdHJpbmcvZnVuY3Rpb24gdHlwZSBhbmQgY2FuIHRocm93IGNvbmZ1c2luZyBlcnJvcnMuXG4gICAgLy8gV2UgZG9uJ3Qgd2FudCBleGNlcHRpb24gYmVoYXZpb3IgdG8gZGlmZmVyIGJldHdlZW4gZGV2IGFuZCBwcm9kLlxuICAgIC8vIChSZW5kZXJpbmcgd2lsbCB0aHJvdyB3aXRoIGEgaGVscGZ1bCBtZXNzYWdlIGFuZCBhcyBzb29uIGFzIHRoZSB0eXBlIGlzXG4gICAgLy8gZml4ZWQsIHRoZSBrZXkgd2FybmluZ3Mgd2lsbCBhcHBlYXIuKVxuXG5cbiAgICBpZiAodmFsaWRUeXBlKSB7XG4gICAgICB2YXIgY2hpbGRyZW4gPSBwcm9wcy5jaGlsZHJlbjtcblxuICAgICAgaWYgKGNoaWxkcmVuICE9PSB1bmRlZmluZWQpIHtcbiAgICAgICAgaWYgKGlzU3RhdGljQ2hpbGRyZW4pIHtcbiAgICAgICAgICBpZiAoaXNBcnJheShjaGlsZHJlbikpIHtcbiAgICAgICAgICAgIGZvciAodmFyIGkgPSAwOyBpIDwgY2hpbGRyZW4ubGVuZ3RoOyBpKyspIHtcbiAgICAgICAgICAgICAgdmFsaWRhdGVDaGlsZEtleXMoY2hpbGRyZW5baV0sIHR5cGUpO1xuICAgICAgICAgICAgfVxuXG4gICAgICAgICAgICBpZiAoT2JqZWN0LmZyZWV6ZSkge1xuICAgICAgICAgICAgICBPYmplY3QuZnJlZXplKGNoaWxkcmVuKTtcbiAgICAgICAgICAgIH1cbiAgICAgICAgICB9IGVsc2Uge1xuICAgICAgICAgICAgZXJyb3IoJ1JlYWN0LmpzeDogU3RhdGljIGNoaWxkcmVuIHNob3VsZCBhbHdheXMgYmUgYW4gYXJyYXkuICcgKyAnWW91IGFyZSBsaWtlbHkgZXhwbGljaXRseSBjYWxsaW5nIFJlYWN0LmpzeHMgb3IgUmVhY3QuanN4REVWLiAnICsgJ1VzZSB0aGUgQmFiZWwgdHJhbnNmb3JtIGluc3RlYWQuJyk7XG4gICAgICAgICAgfVxuICAgICAgICB9IGVsc2Uge1xuICAgICAgICAgIHZhbGlkYXRlQ2hpbGRLZXlzKGNoaWxkcmVuLCB0eXBlKTtcbiAgICAgICAgfVxuICAgICAgfVxuICAgIH1cblxuICAgIHtcbiAgICAgIGlmIChoYXNPd25Qcm9wZXJ0eS5jYWxsKHByb3BzLCAna2V5JykpIHtcbiAgICAgICAgdmFyIGNvbXBvbmVudE5hbWUgPSBnZXRDb21wb25lbnROYW1lRnJvbVR5cGUodHlwZSk7XG4gICAgICAgIHZhciBrZXlzID0gT2JqZWN0LmtleXMocHJvcHMpLmZpbHRlcihmdW5jdGlvbiAoaykge1xuICAgICAgICAgIHJldHVybiBrICE9PSAna2V5JztcbiAgICAgICAgfSk7XG4gICAgICAgIHZhciBiZWZvcmVFeGFtcGxlID0ga2V5cy5sZW5ndGggPiAwID8gJ3trZXk6IHNvbWVLZXksICcgKyBrZXlzLmpvaW4oJzogLi4uLCAnKSArICc6IC4uLn0nIDogJ3trZXk6IHNvbWVLZXl9JztcblxuICAgICAgICBpZiAoIWRpZFdhcm5BYm91dEtleVNwcmVhZFtjb21wb25lbnROYW1lICsgYmVmb3JlRXhhbXBsZV0pIHtcbiAgICAgICAgICB2YXIgYWZ0ZXJFeGFtcGxlID0ga2V5cy5sZW5ndGggPiAwID8gJ3snICsga2V5cy5qb2luKCc6IC4uLiwgJykgKyAnOiAuLi59JyA6ICd7fSc7XG5cbiAgICAgICAgICBlcnJvcignQSBwcm9wcyBvYmplY3QgY29udGFpbmluZyBhIFwia2V5XCIgcHJvcCBpcyBiZWluZyBzcHJlYWQgaW50byBKU1g6XFxuJyArICcgIGxldCBwcm9wcyA9ICVzO1xcbicgKyAnICA8JXMgey4uLnByb3BzfSAvPlxcbicgKyAnUmVhY3Qga2V5cyBtdXN0IGJlIHBhc3NlZCBkaXJlY3RseSB0byBKU1ggd2l0aG91dCB1c2luZyBzcHJlYWQ6XFxuJyArICcgIGxldCBwcm9wcyA9ICVzO1xcbicgKyAnICA8JXMga2V5PXtzb21lS2V5fSB7Li4ucHJvcHN9IC8+JywgYmVmb3JlRXhhbXBsZSwgY29tcG9uZW50TmFtZSwgYWZ0ZXJFeGFtcGxlLCBjb21wb25lbnROYW1lKTtcblxuICAgICAgICAgIGRpZFdhcm5BYm91dEtleVNwcmVhZFtjb21wb25lbnROYW1lICsgYmVmb3JlRXhhbXBsZV0gPSB0cnVlO1xuICAgICAgICB9XG4gICAgICB9XG4gICAgfVxuXG4gICAgaWYgKHR5cGUgPT09IFJFQUNUX0ZSQUdNRU5UX1RZUEUpIHtcbiAgICAgIHZhbGlkYXRlRnJhZ21lbnRQcm9wcyhlbGVtZW50KTtcbiAgICB9IGVsc2Uge1xuICAgICAgdmFsaWRhdGVQcm9wVHlwZXMoZWxlbWVudCk7XG4gICAgfVxuXG4gICAgcmV0dXJuIGVsZW1lbnQ7XG4gIH1cbn0gLy8gVGhlc2UgdHdvIGZ1bmN0aW9ucyBleGlzdCB0byBzdGlsbCBnZXQgY2hpbGQgd2FybmluZ3MgaW4gZGV2XG4vLyBldmVuIHdpdGggdGhlIHByb2QgdHJhbnNmb3JtLiBUaGlzIG1lYW5zIHRoYXQganN4REVWIGlzIHB1cmVseVxuLy8gb3B0LWluIGJlaGF2aW9yIGZvciBiZXR0ZXIgbWVzc2FnZXMgYnV0IHRoYXQgd2Ugd29uJ3Qgc3RvcFxuLy8gZ2l2aW5nIHlvdSB3YXJuaW5ncyBpZiB5b3UgdXNlIHByb2R1Y3Rpb24gYXBpcy5cblxuZnVuY3Rpb24ganN4V2l0aFZhbGlkYXRpb25TdGF0aWModHlwZSwgcHJvcHMsIGtleSkge1xuICB7XG4gICAgcmV0dXJuIGpzeFdpdGhWYWxpZGF0aW9uKHR5cGUsIHByb3BzLCBrZXksIHRydWUpO1xuICB9XG59XG5mdW5jdGlvbiBqc3hXaXRoVmFsaWRhdGlvbkR5bmFtaWModHlwZSwgcHJvcHMsIGtleSkge1xuICB7XG4gICAgcmV0dXJuIGpzeFdpdGhWYWxpZGF0aW9uKHR5cGUsIHByb3BzLCBrZXksIGZhbHNlKTtcbiAgfVxufVxuXG52YXIganN4ID0gIGpzeFdpdGhWYWxpZGF0aW9uRHluYW1pYyA7IC8vIHdlIG1heSB3YW50IHRvIHNwZWNpYWwgY2FzZSBqc3hzIGludGVybmFsbHkgdG8gdGFrZSBhZHZhbnRhZ2Ugb2Ygc3RhdGljIGNoaWxkcmVuLlxuLy8gZm9yIG5vdyB3ZSBjYW4gc2hpcCBpZGVudGljYWwgcHJvZCBmdW5jdGlvbnNcblxudmFyIGpzeHMgPSAganN4V2l0aFZhbGlkYXRpb25TdGF0aWMgO1xuXG5leHBvcnRzLkZyYWdtZW50ID0gUkVBQ1RfRlJBR01FTlRfVFlQRTtcbmV4cG9ydHMuanN4ID0ganN4O1xuZXhwb3J0cy5qc3hzID0ganN4cztcbiAgfSkoKTtcbn1cbiIsIid1c2Ugc3RyaWN0JztcblxuaWYgKHByb2Nlc3MuZW52Lk5PREVfRU5WID09PSAncHJvZHVjdGlvbicpIHtcbiAgbW9kdWxlLmV4cG9ydHMgPSByZXF1aXJlKCcuL2Nqcy9yZWFjdC1qc3gtcnVudGltZS5wcm9kdWN0aW9uLm1pbi5qcycpO1xufSBlbHNlIHtcbiAgbW9kdWxlLmV4cG9ydHMgPSByZXF1aXJlKCcuL2Nqcy9yZWFjdC1qc3gtcnVudGltZS5kZXZlbG9wbWVudC5qcycpO1xufVxuIiwiaW1wb3J0IHsganN4IGFzIF9qc3ggfSBmcm9tIFwicmVhY3QvanN4LXJ1bnRpbWVcIjtcbmltcG9ydCB7IGNyZWF0ZVJlbW90ZVJlYWN0Q29tcG9uZW50IH0gZnJvbSAnQHJlbW90ZS11aS9yZWFjdCc7XG5leHBvcnQgY29uc3QgY3JlYXRlUmVtb3RlQ29tcG9uZW50UmVnaXN0cnkgPSAoKSA9PiB7XG4gICAgY29uc3QgY29tcG9uZW50TWV0YWRhdGFMb29rdXAgPSBuZXcgTWFwKCk7XG4gICAgY29uc3QgY29tcG9uZW50TmFtZUJ5Q29tcG9uZW50TWFwID0gbmV3IE1hcCgpO1xuICAgIGNvbnN0IHJlZ2lzdGVyQ29tcG9uZW50ID0gKGNvbXBvbmVudCwgY29tcG9uZW50TmFtZSwgZnJhZ21lbnRQcm9wcykgPT4ge1xuICAgICAgICBjb21wb25lbnROYW1lQnlDb21wb25lbnRNYXAuc2V0KGNvbXBvbmVudCwgY29tcG9uZW50TmFtZSk7XG4gICAgICAgIGNvbXBvbmVudE1ldGFkYXRhTG9va3VwLnNldChjb21wb25lbnROYW1lLCB7XG4gICAgICAgICAgICBmcmFnbWVudFByb3BzU2V0OiBuZXcgU2V0KGZyYWdtZW50UHJvcHMpLFxuICAgICAgICAgICAgZnJhZ21lbnRQcm9wc0FycmF5OiBmcmFnbWVudFByb3BzLFxuICAgICAgICB9KTtcbiAgICAgICAgcmV0dXJuIGNvbXBvbmVudDtcbiAgICB9O1xuICAgIHJldHVybiB7XG4gICAgICAgIGdldENvbXBvbmVudE5hbWU6IChjb21wb25lbnQpID0+IHtcbiAgICAgICAgICAgIGNvbnN0IGNvbXBvbmVudE5hbWUgPSBjb21wb25lbnROYW1lQnlDb21wb25lbnRNYXAuZ2V0KGNvbXBvbmVudCk7XG4gICAgICAgICAgICBpZiAoIWNvbXBvbmVudE5hbWUpIHtcbiAgICAgICAgICAgICAgICByZXR1cm4gbnVsbDtcbiAgICAgICAgICAgIH1cbiAgICAgICAgICAgIHJldHVybiBjb21wb25lbnROYW1lO1xuICAgICAgICB9LFxuICAgICAgICBpc0FsbG93ZWRDb21wb25lbnROYW1lOiAoY29tcG9uZW50TmFtZSkgPT4ge1xuICAgICAgICAgICAgcmV0dXJuIGNvbXBvbmVudE1ldGFkYXRhTG9va3VwLmhhcyhjb21wb25lbnROYW1lKTtcbiAgICAgICAgfSxcbiAgICAgICAgaXNDb21wb25lbnRGcmFnbWVudFByb3A6IChjb21wb25lbnROYW1lLCBwcm9wTmFtZSkgPT4ge1xuICAgICAgICAgICAgY29uc3QgY29tcG9uZW50TWV0YWRhdGEgPSBjb21wb25lbnRNZXRhZGF0YUxvb2t1cC5nZXQoY29tcG9uZW50TmFtZSk7XG4gICAgICAgICAgICBpZiAoIWNvbXBvbmVudE1ldGFkYXRhKSB7XG4gICAgICAgICAgICAgICAgcmV0dXJuIGZhbHNlO1xuICAgICAgICAgICAgfVxuICAgICAgICAgICAgcmV0dXJuIGNvbXBvbmVudE1ldGFkYXRhLmZyYWdtZW50UHJvcHNTZXQuaGFzKHByb3BOYW1lKTtcbiAgICAgICAgfSxcbiAgICAgICAgZ2V0Q29tcG9uZW50RnJhZ21lbnRQcm9wTmFtZXM6IChjb21wb25lbnROYW1lKSA9PiB7XG4gICAgICAgICAgICBjb25zdCBjb21wb25lbnRNZXRhZGF0YSA9IGNvbXBvbmVudE1ldGFkYXRhTG9va3VwLmdldChjb21wb25lbnROYW1lKTtcbiAgICAgICAgICAgIGlmICghY29tcG9uZW50TWV0YWRhdGEpIHtcbiAgICAgICAgICAgICAgICByZXR1cm4gW107XG4gICAgICAgICAgICB9XG4gICAgICAgICAgICBjb25zdCB7IGZyYWdtZW50UHJvcHNBcnJheSB9ID0gY29tcG9uZW50TWV0YWRhdGE7XG4gICAgICAgICAgICByZXR1cm4gZnJhZ21lbnRQcm9wc0FycmF5O1xuICAgICAgICB9LFxuICAgICAgICBjcmVhdGVBbmRSZWdpc3RlclJlbW90ZVJlYWN0Q29tcG9uZW50OiAoY29tcG9uZW50TmFtZSwgb3B0aW9ucyA9IHt9KSA9PiB7XG4gICAgICAgICAgICBjb25zdCB7IGZyYWdtZW50UHJvcHMgPSBbXSB9ID0gb3B0aW9ucztcbiAgICAgICAgICAgIGNvbnN0IHJlbW90ZVJlYWN0Q29tcG9uZW50ID0gY3JlYXRlUmVtb3RlUmVhY3RDb21wb25lbnQoY29tcG9uZW50TmFtZSwge1xuICAgICAgICAgICAgICAgIGZyYWdtZW50UHJvcHM6IGZyYWdtZW50UHJvcHMsXG4gICAgICAgICAgICB9KTtcbiAgICAgICAgICAgIHJldHVybiByZWdpc3RlckNvbXBvbmVudChyZW1vdGVSZWFjdENvbXBvbmVudCwgY29tcG9uZW50TmFtZSwgZnJhZ21lbnRQcm9wcyk7XG4gICAgICAgIH0sXG4gICAgICAgIGNyZWF0ZUFuZFJlZ2lzdGVyUmVtb3RlQ29tcG91bmRSZWFjdENvbXBvbmVudDogKGNvbXBvbmVudE5hbWUsIG9wdGlvbnMpID0+IHtcbiAgICAgICAgICAgIGNvbnN0IHsgZnJhZ21lbnRQcm9wcyA9IFtdIH0gPSBvcHRpb25zO1xuICAgICAgICAgICAgY29uc3QgUmVtb3RlQ29tcG9uZW50VHlwZSA9IGNyZWF0ZVJlbW90ZVJlYWN0Q29tcG9uZW50KGNvbXBvbmVudE5hbWUsIHtcbiAgICAgICAgICAgICAgICBmcmFnbWVudFByb3BzLFxuICAgICAgICAgICAgfSk7XG4gICAgICAgICAgICAvLyBXZSBjYW4gb25seSBhdHRhY2ggcHJvcGVydGllcyB0byBhIGZ1bmN0aW9uIGNvbXBvbmVudCB0eXBlLCBzbyB3ZSBuZWVkIHRvIGNoZWNrIGlmIHRoZSByZW1vdGUgY29tcG9uZW50IHR5cGUgaXMgYSBmdW5jdGlvbi5cbiAgICAgICAgICAgIC8vIElmIHRoZSByZW1vdGUgY29tcG9uZW50IHR5cGUgaXMgbm90IGEgZnVuY3Rpb24sIHdlIG5lZWQgdG8gd3JhcCBpdCBpbiBhIGZ1bmN0aW9uIGNvbXBvbmVudC5cbiAgICAgICAgICAgIGNvbnN0IENvbXBvdW5kRnVuY3Rpb25Db21wb25lbnRUeXBlID0gdHlwZW9mIFJlbW90ZUNvbXBvbmVudFR5cGUgPT09ICdmdW5jdGlvbidcbiAgICAgICAgICAgICAgICA/IFJlbW90ZUNvbXBvbmVudFR5cGVcbiAgICAgICAgICAgICAgICA6IChwcm9wcykgPT4gKF9qc3goUmVtb3RlQ29tcG9uZW50VHlwZSwgeyAuLi5wcm9wcyB9KSk7XG4gICAgICAgICAgICAvLyBBdHRhY2ggdGhlIGNvbXBvdW5kIGNvbXBvbmVudCBwcm9wZXJ0aWVzIHRvIHRoZSBmdW5jdGlvbiBjb21wb25lbnQgdGhhdCB3ZSB3aWxsIGJlIHJldHVybmluZy5cbiAgICAgICAgICAgIE9iamVjdC5hc3NpZ24oQ29tcG91bmRGdW5jdGlvbkNvbXBvbmVudFR5cGUsIG9wdGlvbnMuY29tcG91bmRDb21wb25lbnRQcm9wZXJ0aWVzKTtcbiAgICAgICAgICAgIC8vIFJlZ2lzdGVyIHRoZSBjb21wb3VuZCBmdW5jdGlvbiBjb21wb25lbnQgd2l0aCB0aGUgcmVnaXN0cnkgYW5kIHJldHVybiBpdC5cbiAgICAgICAgICAgIHJldHVybiByZWdpc3RlckNvbXBvbmVudChDb21wb3VuZEZ1bmN0aW9uQ29tcG9uZW50VHlwZSwgY29tcG9uZW50TmFtZSwgZnJhZ21lbnRQcm9wcyk7XG4gICAgICAgIH0sXG4gICAgfTtcbn07XG4iLCJpbXBvcnQgeyBjcmVhdGVSZW1vdGVDb21wb25lbnRSZWdpc3RyeSB9IGZyb20gXCIuL3V0aWxzL3JlbW90ZS1jb21wb25lbnQtcmVnaXN0cnkuanNcIjtcbi8qKlxuICogUmVwcmVzZW50cyBhIHJlZ2lzdHJ5IG9mIEh1YlNwb3QtcHJvdmlkZWQgUmVhY3QgY29tcG9uZW50cyB0aGF0IHNob3VsZCBvbmx5IGJlIHVzZWQgKippbnRlcm5hbGx5KiogYnkgdGhlIFVJIGV4dGVuc2lvbiBTREsuXG4gKlxuICogQGludGVybmFsXG4gKi9cbmV4cG9ydCBjb25zdCBfX2h1YlNwb3RDb21wb25lbnRSZWdpc3RyeSA9IGNyZWF0ZVJlbW90ZUNvbXBvbmVudFJlZ2lzdHJ5KCk7XG5jb25zdCB7IGNyZWF0ZUFuZFJlZ2lzdGVyUmVtb3RlUmVhY3RDb21wb25lbnQsIGNyZWF0ZUFuZFJlZ2lzdGVyUmVtb3RlQ29tcG91bmRSZWFjdENvbXBvbmVudCwgfSA9IF9faHViU3BvdENvbXBvbmVudFJlZ2lzdHJ5O1xuLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vXG4vLyBTVEFOREFSRCBDT01QT05FTlRTXG4vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy9cbi8qKlxuICogVGhlIGBBbGVydGAgY29tcG9uZW50IHJlbmRlcnMgYW4gYWxlcnQgd2l0aGluIGEgY2FyZC4gVXNlIHRoaXMgY29tcG9uZW50IHRvIGdpdmUgdXNhZ2UgZ3VpZGFuY2UsIG5vdGlmeSB1c2VycyBvZiBhY3Rpb24gcmVzdWx0cywgb3Igd2FybiB0aGVtIGFib3V0IHBvdGVudGlhbCBpc3N1ZXMgb3IgZmFpbHVyZXMuXG4gKlxuICogKipMaW5rczoqKlxuICpcbiAqIC0ge0BsaW5rIGh0dHBzOi8vZGV2ZWxvcGVycy5odWJzcG90LmNvbS9kb2NzL3JlZmVyZW5jZS91aS1jb21wb25lbnRzL3N0YW5kYXJkLWNvbXBvbmVudHMvYWxlcnQgRG9jc31cbiAqIC0ge0BsaW5rIGh0dHBzOi8vYXBwLmh1YnNwb3QuY29tL2RvY3MvNDgwMDg5MTYvcmVmZXJlbmNlL3VpLWNvbXBvbmVudHMvc3RhbmRhcmQtY29tcG9uZW50cy9hbGVydCN2YXJpYW50cyBWYXJpYW50c31cbiAqL1xuZXhwb3J0IGNvbnN0IEFsZXJ0ID0gY3JlYXRlQW5kUmVnaXN0ZXJSZW1vdGVSZWFjdENvbXBvbmVudCgnQWxlcnQnKTtcbi8qKlxuICogVGhlIGBCdXR0b25gIGNvbXBvbmVudCByZW5kZXJzIGEgc2luZ2xlIGJ1dHRvbi4gVXNlIHRoaXMgY29tcG9uZW50IHRvIGVuYWJsZSB1c2VycyB0byBwZXJmb3JtIGFjdGlvbnMsIHN1Y2ggYXMgc3VibWl0dGluZyBhIGZvcm0sIHNlbmRpbmcgZGF0YSB0byBhbiBleHRlcm5hbCBzeXN0ZW0sIG9yIGRlbGV0aW5nIGRhdGEuXG4gKlxuICogKipMaW5rczoqKlxuICpcbiAqIC0ge0BsaW5rIGh0dHBzOi8vZGV2ZWxvcGVycy5odWJzcG90LmNvbS9kb2NzL3JlZmVyZW5jZS91aS1jb21wb25lbnRzL3N0YW5kYXJkLWNvbXBvbmVudHMvYnV0dG9uIERvY3N9XG4gKiAtIHtAbGluayBodHRwczovL2RldmVsb3BlcnMuaHVic3BvdC5jb20vZG9jcy9yZWZlcmVuY2UvdWktY29tcG9uZW50cy9zdGFuZGFyZC1jb21wb25lbnRzL2J1dHRvbiN1c2FnZS1leGFtcGxlcyBFeGFtcGxlc31cbiAqIC0ge0BsaW5rIGh0dHBzOi8vZ2l0aHViLmNvbS9IdWJTcG90L3VpLWV4dGVuc2lvbnMtZXhhbXBsZXMvdHJlZS9tYWluL2Rlc2lnbi1wYXR0ZXJucyNidXR0b24gRGVzaWduIFBhdHRlcm4gRXhhbXBsZXN9XG4gKi9cbmV4cG9ydCBjb25zdCBCdXR0b24gPSBjcmVhdGVBbmRSZWdpc3RlclJlbW90ZVJlYWN0Q29tcG9uZW50KCdCdXR0b24nLCB7XG4gICAgZnJhZ21lbnRQcm9wczogWydvdmVybGF5J10sXG59KTtcbi8qKlxuICogVGhlIGBCdXR0b25Sb3dgIGNvbXBvbmVudCByZW5kZXJzIGEgcm93IG9mIHNwZWNpZmllZCBgQnV0dG9uYCBjb21wb25lbnRzLiBVc2UgdGhpcyBjb21wb25lbnQgd2hlbiB5b3Ugd2FudCB0byBpbmNsdWRlIG11bHRpcGxlIGJ1dHRvbnMgaW4gYSByb3cuXG4gKlxuICogKipMaW5rczoqKlxuICpcbiAqIC0ge0BsaW5rIGh0dHBzOi8vZGV2ZWxvcGVycy5odWJzcG90LmNvbS9kb2NzL3JlZmVyZW5jZS91aS1jb21wb25lbnRzL3N0YW5kYXJkLWNvbXBvbmVudHMvYnV0dG9uLXJvdyBEb2NzfVxuICovXG5leHBvcnQgY29uc3QgQnV0dG9uUm93ID0gY3JlYXRlQW5kUmVnaXN0ZXJSZW1vdGVSZWFjdENvbXBvbmVudCgnQnV0dG9uUm93Jyk7XG5leHBvcnQgY29uc3QgQ2FyZCA9IGNyZWF0ZUFuZFJlZ2lzdGVyUmVtb3RlUmVhY3RDb21wb25lbnQoJ0NhcmQnKTtcbi8qKlxuICogVGhlIGBEZXNjcmlwdGlvbkxpc3RgIGNvbXBvbmVudCByZW5kZXJzIHBhaXJzIG9mIGxhYmVscyBhbmQgdmFsdWVzLiBVc2UgdGhpcyBjb21wb25lbnQgdG8gZGlzcGxheSBwYWlycyBvZiBsYWJlbHMgYW5kIHZhbHVlcyBpbiBhIHdheSB0aGF0J3MgZWFzeSB0byByZWFkIGF0IGEgZ2xhbmNlLlxuICpcbiAqICoqTGlua3M6KipcbiAqXG4gKiAtIHtAbGluayBodHRwczovL2RldmVsb3BlcnMuaHVic3BvdC5jb20vZG9jcy9yZWZlcmVuY2UvdWktY29tcG9uZW50cy9zdGFuZGFyZC1jb21wb25lbnRzL2Rlc2NyaXB0aW9uLWxpc3QgRG9jc31cbiAqL1xuZXhwb3J0IGNvbnN0IERlc2NyaXB0aW9uTGlzdCA9IGNyZWF0ZUFuZFJlZ2lzdGVyUmVtb3RlUmVhY3RDb21wb25lbnQoJ0Rlc2NyaXB0aW9uTGlzdCcpO1xuLyoqXG4gKiBUaGUgYERlc2NyaXB0aW9uTGlzdEl0ZW1gIGNvbXBvbmVudCByZW5kZXJzIGEgc2luZ2xlIHNldCBvZiBhIGxhYmVsIGFuZCB2YWx1ZS4gVXNlIHRoaXMgY29tcG9uZW50IHdpdGhpbiBhIGBEZXNjcmlwdGlvbkxpc3RgIGNvbXBvbmVudC5cbiAqXG4gKiAqKkxpbmtzOioqXG4gKlxuICogLSB7QGxpbmsgaHR0cHM6Ly9kZXZlbG9wZXJzLmh1YnNwb3QuY29tL2RvY3MvcmVmZXJlbmNlL3VpLWNvbXBvbmVudHMvc3RhbmRhcmQtY29tcG9uZW50cy9kZXNjcmlwdGlvbi1saXN0IERvY3N9XG4gKi9cbmV4cG9ydCBjb25zdCBEZXNjcmlwdGlvbkxpc3RJdGVtID0gY3JlYXRlQW5kUmVnaXN0ZXJSZW1vdGVSZWFjdENvbXBvbmVudCgnRGVzY3JpcHRpb25MaXN0SXRlbScpO1xuLyoqXG4gKiBUaGUgYERpdmlkZXJgIGNvbXBvbmVudCByZW5kZXJzIGEgZ3JleSwgaG9yaXpvbnRhbCBsaW5lIGZvciBzcGFjaW5nIG91dCBjb21wb25lbnRzIHZlcnRpY2FsbHkgb3IgY3JlYXRpbmcgc2VjdGlvbnMgaW4gYW4gZXh0ZW5zaW9uLiBVc2UgdGhpcyBjb21wb25lbnQgdG8gc3BhY2Ugb3V0IG90aGVyIGNvbXBvbmVudHMgd2hlbiB0aGUgY29udGVudCBuZWVkcyBtb3JlIHNlcGFyYXRpb24gdGhhbiB3aGl0ZSBzcGFjZS5cbiAqXG4gKiAqKkxpbmtzOioqXG4gKlxuICogLSB7QGxpbmsgaHR0cHM6Ly9kZXZlbG9wZXJzLmh1YnNwb3QuY29tL2RvY3MvcmVmZXJlbmNlL3VpLWNvbXBvbmVudHMvc3RhbmRhcmQtY29tcG9uZW50cy9kaXZpZGVyIERvY3N9XG4gKi9cbmV4cG9ydCBjb25zdCBEaXZpZGVyID0gY3JlYXRlQW5kUmVnaXN0ZXJSZW1vdGVSZWFjdENvbXBvbmVudCgnRGl2aWRlcicpO1xuLyoqXG4gKiBUaGUgYFNwYWNlcmAgY29tcG9uZW50IHJlbmRlcnMgdmVydGljYWwgc3BhY2UgYmV0d2VlbiBjb21wb25lbnRzLiBVc2UgdGhpcyBjb21wb25lbnRcbiAqIHRvIGFkZCBjb25zaXN0ZW50IHNwYWNpbmcgd2l0aG91dCB1c2luZyBlbXB0eSB3cmFwcGVyIGNvbXBvbmVudHMuXG4gKlxuICogKipMaW5rczoqKlxuICpcbiAqIC0ge0BsaW5rIGh0dHBzOi8vZGV2ZWxvcGVycy5odWJzcG90LmNvbS9kb2NzL3JlZmVyZW5jZS91aS1jb21wb25lbnRzL3N0YW5kYXJkLWNvbXBvbmVudHMvc3BhY2VyIERvY3N9XG4gKi9cbmV4cG9ydCBjb25zdCBTcGFjZXIgPSBjcmVhdGVBbmRSZWdpc3RlclJlbW90ZVJlYWN0Q29tcG9uZW50KCdTcGFjZXInKTtcbi8qKlxuICogVGhlIGBFbXB0eVN0YXRlYCBjb21wb25lbnQgc2V0cyB0aGUgY29udGVudCB0aGF0IGFwcGVhcnMgd2hlbiB0aGUgZXh0ZW5zaW9uIGlzIGluIGFuIGVtcHR5IHN0YXRlLiBVc2UgdGhpcyBjb21wb25lbnQgd2hlbiB0aGVyZSdzIG5vIGNvbnRlbnQgb3IgZGF0YSB0byBoZWxwIGd1aWRlIHVzZXJzLlxuICpcbiAqICoqTGlua3M6KipcbiAqXG4gKiAtIHtAbGluayBodHRwczovL2RldmVsb3BlcnMuaHVic3BvdC5jb20vZG9jcy9yZWZlcmVuY2UvdWktY29tcG9uZW50cy9zdGFuZGFyZC1jb21wb25lbnRzL2VtcHR5LXN0YXRlIERvY3N9XG4gKi9cbmV4cG9ydCBjb25zdCBFbXB0eVN0YXRlID0gY3JlYXRlQW5kUmVnaXN0ZXJSZW1vdGVSZWFjdENvbXBvbmVudCgnRW1wdHlTdGF0ZScpO1xuLyoqXG4gKiBUaGUgYEVycm9yU3RhdGVgIGNvbXBvbmVudCBzZXRzIHRoZSBjb250ZW50IG9mIGFuIGVycm9yaW5nIGV4dGVuc2lvbi4gVXNlIHRoaXMgY29tcG9uZW50IHRvIGd1aWRlIHVzZXJzIHRocm91Z2ggcmVzb2x2aW5nIGVycm9ycyB0aGF0IHlvdXIgZXh0ZW5zaW9uIG1pZ2h0IGVuY291bnRlci5cbiAqXG4gKiAqKkxpbmtzOioqXG4gKlxuICogLSB7QGxpbmsgaHR0cHM6Ly9kZXZlbG9wZXJzLmh1YnNwb3QuY29tL2RvY3MvcmVmZXJlbmNlL3VpLWNvbXBvbmVudHMvc3RhbmRhcmQtY29tcG9uZW50cy9lcnJvci1zdGF0ZSBEb2NzfVxuICovXG5leHBvcnQgY29uc3QgRXJyb3JTdGF0ZSA9IGNyZWF0ZUFuZFJlZ2lzdGVyUmVtb3RlUmVhY3RDb21wb25lbnQoJ0Vycm9yU3RhdGUnKTtcbi8qKlxuICogVGhlIGBGb3JtYCBjb21wb25lbnQgcmVuZGVycyBhIGZvcm0gdGhhdCBjYW4gY29udGFpbiBvdGhlciBzdWJjb21wb25lbnRzLCBzdWNoIGFzIGBJbnB1dGAsIGBTZWxlY3RgLCBhbmQgYEJ1dHRvbmAuIFVzZSB0aGlzIGNvbXBvbmVudCB0byBlbmFibGUgdXNlcnMgdG8gc3VibWl0IGRhdGEgdG8gSHViU3BvdCBvciBhbiBleHRlcm5hbCBzeXN0ZW0uXG4gKlxuICogKipMaW5rczoqKlxuICpcbiAqIC0ge0BsaW5rIGh0dHBzOi8vZGV2ZWxvcGVycy5odWJzcG90LmNvbS9kb2NzL3JlZmVyZW5jZS91aS1jb21wb25lbnRzL3N0YW5kYXJkLWNvbXBvbmVudHMvZm9ybSBEb2NzfVxuICogLSB7QGxpbmsgaHR0cHM6Ly9naXRodWIuY29tL0h1YlNwb3QvdWktZXh0ZW5zaW9ucy1leGFtcGxlcy90cmVlL21haW4vZGVzaWduLXBhdHRlcm5zI2Zvcm0gRGVzaWduIFBhdHRlcm4gRXhhbXBsZXN9XG4gKi9cbmV4cG9ydCBjb25zdCBGb3JtID0gY3JlYXRlQW5kUmVnaXN0ZXJSZW1vdGVSZWFjdENvbXBvbmVudCgnRm9ybScpO1xuLyoqXG4gKiBUaGUgYEhlYWRpbmdgIGNvbXBvbmVudCByZW5kZXJzIGxhcmdlIGhlYWRpbmcgdGV4dC4gVXNlIHRoaXMgY29tcG9uZW50IHRvIGludHJvZHVjZSBvciBkaWZmZXJlbnRpYXRlIHNlY3Rpb25zIG9mIHlvdXIgY29tcG9uZW50LlxuICpcbiAqICoqTGlua3M6KipcbiAqXG4gKiAtIHtAbGluayBodHRwczovL2RldmVsb3BlcnMuaHVic3BvdC5jb20vZG9jcy9yZWZlcmVuY2UvdWktY29tcG9uZW50cy9zdGFuZGFyZC1jb21wb25lbnRzL2hlYWRpbmcgRG9jc31cbiAqL1xuZXhwb3J0IGNvbnN0IEhlYWRpbmcgPSBjcmVhdGVBbmRSZWdpc3RlclJlbW90ZVJlYWN0Q29tcG9uZW50KCdIZWFkaW5nJyk7XG4vKipcbiAqIFRoZSBgSW1hZ2VgIGNvbXBvbmVudCByZW5kZXJzIGFuIGltYWdlLiBVc2UgdGhpcyBjb21wb25lbnQgdG8gYWRkIGEgbG9nbyBvciBvdGhlciB2aXN1YWwgYnJhbmQgaWRlbnRpdHkgYXNzZXQsIG9yIHRvIGFjY2VudHVhdGUgb3RoZXIgY29udGVudCBpbiB0aGUgZXh0ZW5zaW9uLlxuICpcbiAqICoqTGlua3M6KipcbiAqXG4gKiAtIHtAbGluayBodHRwczovL2RldmVsb3BlcnMuaHVic3BvdC5jb20vZG9jcy9yZWZlcmVuY2UvdWktY29tcG9uZW50cy9zdGFuZGFyZC1jb21wb25lbnRzL2ltYWdlIERvY3N9XG4gKi9cbmV4cG9ydCBjb25zdCBJbWFnZSA9IGNyZWF0ZUFuZFJlZ2lzdGVyUmVtb3RlUmVhY3RDb21wb25lbnQoJ0ltYWdlJywge1xuICAgIGZyYWdtZW50UHJvcHM6IFsnb3ZlcmxheSddLFxufSk7XG4vKipcbiAqIFRoZSBgSW5wdXRgIGNvbXBvbmVudCByZW5kZXJzIGEgdGV4dCBpbnB1dCBmaWVsZCB3aGVyZSBhIHVzZXIgY2FuIGVudGVyIGEgY3VzdG9tIHRleHQgdmFsdWUuIExpa2Ugb3RoZXIgaW5wdXRzLCB0aGlzIGNvbXBvbmVudCBzaG91bGQgYmUgdXNlZCB3aXRoaW4gYSBgRm9ybWAgdGhhdCBoYXMgYSBzdWJtaXQgYnV0dG9uLlxuICpcbiAqICoqTGlua3M6KipcbiAqXG4gKiAtIHtAbGluayBodHRwczovL2RldmVsb3BlcnMuaHVic3BvdC5jb20vZG9jcy9yZWZlcmVuY2UvdWktY29tcG9uZW50cy9zdGFuZGFyZC1jb21wb25lbnRzL2lucHV0IERvY3N9XG4gKi9cbmV4cG9ydCBjb25zdCBJbnB1dCA9IGNyZWF0ZUFuZFJlZ2lzdGVyUmVtb3RlUmVhY3RDb21wb25lbnQoJ0lucHV0Jyk7XG4vKipcbiAqIFRoZSBgTGlua2AgY29tcG9uZW50IHJlbmRlcnMgYSBjbGlja2FibGUgaHlwZXJsaW5rLiBVc2UgbGlua3MgdG8gZGlyZWN0IHVzZXJzIHRvIGFuIGV4dGVybmFsIHdlYiBwYWdlIG9yIGFub3RoZXIgcGFydCBvZiB0aGUgSHViU3BvdCBhcHAuXG4gKlxuICogKipMaW5rczoqKlxuICpcbiAqIC0ge0BsaW5rIGh0dHBzOi8vZGV2ZWxvcGVycy5odWJzcG90LmNvbS9kb2NzL3JlZmVyZW5jZS91aS1jb21wb25lbnRzL3N0YW5kYXJkLWNvbXBvbmVudHMvbGluayBEb2NzfVxuICovXG5leHBvcnQgY29uc3QgTGluayA9IGNyZWF0ZUFuZFJlZ2lzdGVyUmVtb3RlUmVhY3RDb21wb25lbnQoJ0xpbmsnLCB7XG4gICAgZnJhZ21lbnRQcm9wczogWydvdmVybGF5J10sXG59KTtcbi8qKlxuICogVGhlIGBUZXh0QXJlYWAgY29tcG9uZW50IHJlbmRlcnMgYSBmaWxsYWJsZSB0ZXh0IGZpZWxkLiBMaWtlIG90aGVyIGlucHV0cywgdGhpcyBjb21wb25lbnQgc2hvdWxkIGJlIHVzZWQgd2l0aGluIGEgYEZvcm1gIHRoYXQgaGFzIGEgc3VibWl0IGJ1dHRvbi5cbiAqXG4gKiAqKkxpbmtzOioqXG4gKlxuICogLSB7QGxpbmsgaHR0cHM6Ly9kZXZlbG9wZXJzLmh1YnNwb3QuY29tL2RvY3MvcmVmZXJlbmNlL3VpLWNvbXBvbmVudHMvc3RhbmRhcmQtY29tcG9uZW50cy90ZXh0LWFyZWEgRG9jc31cbiAqL1xuZXhwb3J0IGNvbnN0IFRleHRBcmVhID0gY3JlYXRlQW5kUmVnaXN0ZXJSZW1vdGVSZWFjdENvbXBvbmVudCgnVGV4dEFyZWEnKTtcbi8vIFRleHRhcmVhIHdhcyBjaGFuZ2VkIHRvIFRleHRBcmVhXG4vLyBFeHBvcnRpbmcgYm90aCBmb3IgYmFja3dhcmRzIGNvbXBhdFxuLyoqIEBkZXByZWNhdGVkIHVzZSBUZXh0QXJlYSBpbnN0ZWFkLiBXaXRoIGEgY2FwaXRhbCBBLiovXG5leHBvcnQgY29uc3QgVGV4dGFyZWEgPSBjcmVhdGVBbmRSZWdpc3RlclJlbW90ZVJlYWN0Q29tcG9uZW50KCdUZXh0YXJlYScpO1xuLyoqXG4gKiBUaGUgYExvYWRpbmdTcGlubmVyYCBjb21wb25lbnQgcmVuZGVycyBhIHZpc3VhbCBpbmRpY2F0b3IgZm9yIHdoZW4gYW4gZXh0ZW5zaW9uIGlzIGxvYWRpbmcgb3IgcHJvY2Vzc2luZyBkYXRhLlxuICpcbiAqICoqTGlua3M6KipcbiAqXG4gKiAtIHtAbGluayBodHRwczovL2RldmVsb3BlcnMuaHVic3BvdC5jb20vZG9jcy9yZWZlcmVuY2UvdWktY29tcG9uZW50cy9zdGFuZGFyZC1jb21wb25lbnRzL2xvYWRpbmctc3Bpbm5lciBEb2NzfVxuICovXG5leHBvcnQgY29uc3QgTG9hZGluZ1NwaW5uZXIgPSBjcmVhdGVBbmRSZWdpc3RlclJlbW90ZVJlYWN0Q29tcG9uZW50KCdMb2FkaW5nU3Bpbm5lcicpO1xuLyoqXG4gKiBUaGUgYFByb2dyZXNzQmFyYCBjb21wb25lbnQgcmVuZGVycyBhIHZpc3VhbCBpbmRpY2F0b3Igc2hvd2luZyBhIG51bWVyaWMgYW5kL29yIHBlcmNlbnRhZ2UtYmFzZWQgcmVwcmVzZW50YXRpb24gb2YgcHJvZ3Jlc3MuIFRoZSBwZXJjZW50YWdlIGlzIGNhbGN1bGF0ZWQgYmFzZWQgb24gdGhlIG1heGltdW0gcG9zc2libGUgdmFsdWUgc3BlY2lmaWVkIGluIHRoZSBjb21wb25lbnQuXG4gKlxuICogKipMaW5rczoqKlxuICpcbiAqIC0ge0BsaW5rIGh0dHBzOi8vZGV2ZWxvcGVycy5odWJzcG90LmNvbS9kb2NzL3JlZmVyZW5jZS91aS1jb21wb25lbnRzL3N0YW5kYXJkLWNvbXBvbmVudHMvcHJvZ3Jlc3MtYmFyIERvY3N9XG4gKi9cbmV4cG9ydCBjb25zdCBQcm9ncmVzc0JhciA9IGNyZWF0ZUFuZFJlZ2lzdGVyUmVtb3RlUmVhY3RDb21wb25lbnQoJ1Byb2dyZXNzQmFyJyk7XG4vKipcbiAqIFRoZSBgU2VsZWN0YCBjb21wb25lbnQgcmVuZGVycyBhIGRyb3Bkb3duIG1lbnUgc2VsZWN0IGZpZWxkIHdoZXJlIGEgdXNlciBjYW4gc2VsZWN0IGEgc2luZ2xlIHZhbHVlLiBBIHNlYXJjaCBiYXIgd2lsbCBiZSBhdXRvbWF0aWNhbGx5IGluY2x1ZGVkIHdoZW4gdGhlcmUgYXJlIG1vcmUgdGhhbiBzZXZlbiBvcHRpb25zLiBMaWtlIG90aGVyIGlucHV0cywgdGhpcyBjb21wb25lbnQgc2hvdWxkIGJlIHVzZWQgd2l0aGluIGEgYEZvcm1gIHRoYXQgaGFzIGEgc3VibWl0IGJ1dHRvbi5cbiAqXG4gKiAqKkxpbmtzOioqXG4gKlxuICogLSB7QGxpbmsgaHR0cHM6Ly9kZXZlbG9wZXJzLmh1YnNwb3QuY29tL2RvY3MvcmVmZXJlbmNlL3VpLWNvbXBvbmVudHMvc3RhbmRhcmQtY29tcG9uZW50cy9zZWxlY3QgRG9jc31cbiAqL1xuZXhwb3J0IGNvbnN0IFNlbGVjdCA9IGNyZWF0ZUFuZFJlZ2lzdGVyUmVtb3RlUmVhY3RDb21wb25lbnQoJ1NlbGVjdCcpO1xuLyoqXG4gKiBUaGUgYFRhZ2AgY29tcG9uZW50IHJlbmRlcnMgYSB0YWcgdG8gbGFiZWwgb3IgY2F0ZWdvcml6ZSBpbmZvcm1hdGlvbiBvciBvdGhlciBjb21wb25lbnRzLiBUYWdzIGNhbiBiZSBzdGF0aWMgb3IgY2xpY2thYmxlIGZvciBpbnZva2luZyBmdW5jdGlvbnMuXG4gKlxuICogKipMaW5rczoqKlxuICpcbiAqIC0ge0BsaW5rIGh0dHBzOi8vZGV2ZWxvcGVycy5odWJzcG90LmNvbS9kb2NzL3JlZmVyZW5jZS91aS1jb21wb25lbnRzL3N0YW5kYXJkLWNvbXBvbmVudHMvdGFnIERvY3N9XG4gKi9cbmV4cG9ydCBjb25zdCBUYWcgPSBjcmVhdGVBbmRSZWdpc3RlclJlbW90ZVJlYWN0Q29tcG9uZW50KCdUYWcnLCB7XG4gICAgZnJhZ21lbnRQcm9wczogWydvdmVybGF5J10sXG59KTtcbi8qKlxuICogVGhlIGBUZXh0YCBjb21wb25lbnQgcmVuZGVycyB0ZXh0IHdpdGggZm9ybWF0dGluZyBvcHRpb25zLlxuICpcbiAqICoqTGlua3M6KipcbiAqXG4gKiAtIHtAbGluayBodHRwczovL2RldmVsb3BlcnMuaHVic3BvdC5jb20vZG9jcy9yZWZlcmVuY2UvdWktY29tcG9uZW50cy9zdGFuZGFyZC1jb21wb25lbnRzL3RleHQgRG9jc31cbiAqL1xuZXhwb3J0IGNvbnN0IFRleHQgPSBjcmVhdGVBbmRSZWdpc3RlclJlbW90ZVJlYWN0Q29tcG9uZW50KCdUZXh0Jyk7XG4vKipcbiAqIFRoZSBgVGlsZWAgY29tcG9uZW50IHJlbmRlcnMgYSBzcXVhcmUgdGlsZSB0aGF0IGNhbiBjb250YWluIG90aGVyIGNvbXBvbmVudHMuIFVzZSB0aGlzIGNvbXBvbmVudCB0byBjcmVhdGUgZ3JvdXBzIG9mIHJlbGF0ZWQgY29tcG9uZW50cy5cbiAqXG4gKiAqKkxpbmtzOioqXG4gKlxuICogLSB7QGxpbmsgaHR0cHM6Ly9kZXZlbG9wZXJzLmh1YnNwb3QuY29tL2RvY3MvcmVmZXJlbmNlL3VpLWNvbXBvbmVudHMvc3RhbmRhcmQtY29tcG9uZW50cy90aWxlIERvY3N9XG4gKi9cbmV4cG9ydCBjb25zdCBUaWxlID0gY3JlYXRlQW5kUmVnaXN0ZXJSZW1vdGVSZWFjdENvbXBvbmVudCgnVGlsZScpO1xuLyoqIEBkZXByZWNhdGVkIHVzZSBGbGV4IGluc3RlYWQuIEl0IHdpbGwgYmUgcmVtb3ZlZCBpbiB0aGUgbmV4dCByZWxlYXNlLiAqL1xuZXhwb3J0IGNvbnN0IFN0YWNrID0gY3JlYXRlQW5kUmVnaXN0ZXJSZW1vdGVSZWFjdENvbXBvbmVudCgnU3RhY2snKTtcbi8qKlxuICogVGhlIGBUb2dnbGVHcm91cGAgY29tcG9uZW50IHJlbmRlcnMgYSBsaXN0IG9mIHNlbGVjdGFibGUgb3B0aW9ucywgZWl0aGVyIGluIHJhZGlvIGJ1dHRvbiBvciBjaGVja2JveCBmb3JtLlxuICpcbiAqICoqTGlua3M6KipcbiAqXG4gKiAtIHtAbGluayBodHRwczovL2RldmVsb3BlcnMuaHVic3BvdC5jb20vZG9jcy9yZWZlcmVuY2UvdWktY29tcG9uZW50cy9zdGFuZGFyZC1jb21wb25lbnRzL3RvZ2dsZS1ncm91cCBEb2NzfVxuICovXG5leHBvcnQgY29uc3QgVG9nZ2xlR3JvdXAgPSBjcmVhdGVBbmRSZWdpc3RlclJlbW90ZVJlYWN0Q29tcG9uZW50KCdUb2dnbGVHcm91cCcpO1xuLyoqXG4gKiBUaGUgYFN0YXRpc3RpY3NJdGVtYCBjb21wb25lbnQgcmVuZGVycyBhIHNpbmdsZSBkYXRhIHBvaW50IHdpdGhpbiBhIGBTdGF0aXN0aWNzYCBjb21wb25lbnQuIFVzZSB0aGlzIGNvbXBvbmVudCB0byBkaXNwbGF5IGEgc2luZ2xlIGRhdGEgcG9pbnQsIHN1Y2ggYXMgYSBudW1iZXIgb3IgcGVyY2VudGFnZS5cbiAqXG4gKiAqKkxpbmtzOioqXG4gKlxuICogLSB7QGxpbmsgaHR0cHM6Ly9kZXZlbG9wZXJzLmh1YnNwb3QuY29tL2RvY3MvcmVmZXJlbmNlL3VpLWNvbXBvbmVudHMvc3RhbmRhcmQtY29tcG9uZW50cy9zdGF0aXN0aWNzIERvY3N9XG4gKi9cbmV4cG9ydCBjb25zdCBTdGF0aXN0aWNzSXRlbSA9IGNyZWF0ZUFuZFJlZ2lzdGVyUmVtb3RlUmVhY3RDb21wb25lbnQoJ1N0YXRpc3RpY3NJdGVtJyk7XG4vKipcbiAqIFRoZSBgU3RhdGlzdGljc2AgY29tcG9uZW50IHJlbmRlcnMgYSB2aXN1YWwgc3BvdGxpZ2h0IG9mIG9uZSBvciBtb3JlIGRhdGEgcG9pbnRzLiBJbmNsdWRlcyB0aGUgYFN0YXRpc3RpY3NJdGVtYCBhbmQgYFN0YXRpc3RpY3NUcmVuZGAgc3ViY29tcG9uZW50cy5cbiAqXG4gKiAqKkxpbmtzOioqXG4gKlxuICogLSB7QGxpbmsgaHR0cHM6Ly9kZXZlbG9wZXJzLmh1YnNwb3QuY29tL2RvY3MvcmVmZXJlbmNlL3VpLWNvbXBvbmVudHMvc3RhbmRhcmQtY29tcG9uZW50cy9zdGF0aXN0aWNzIERvY3N9XG4gKi9cbmV4cG9ydCBjb25zdCBTdGF0aXN0aWNzID0gY3JlYXRlQW5kUmVnaXN0ZXJSZW1vdGVSZWFjdENvbXBvbmVudCgnU3RhdGlzdGljcycpO1xuLyoqXG4gKiBUaGUgYFN0YXRpc3RpY3NUcmVuZGAgY29tcG9uZW50IHJlbmRlcnMgYSBwZXJjZW50YWdlIHRyZW5kIHZhbHVlIGFuZCBkaXJlY3Rpb24gYWxvbnNpZGUgYSBgU3RhdGlzdGljc0l0ZW1gIGNvbXBvbmVudC4gVXNlIHRoaXMgY29tcG9uZW50IHdpdGhpbiB0aGUgYFN0YXRpc3RpY3NJdGVtYCBjb21wb25lbnQuXG4gKlxuICogKipMaW5rczoqKlxuICpcbiAqIC0ge0BsaW5rIGh0dHBzOi8vZGV2ZWxvcGVycy5odWJzcG90LmNvbS9kb2NzL3JlZmVyZW5jZS91aS1jb21wb25lbnRzL3N0YW5kYXJkLWNvbXBvbmVudHMvc3RhdGlzdGljcyBEb2NzfVxuICovXG5leHBvcnQgY29uc3QgU3RhdGlzdGljc1RyZW5kID0gY3JlYXRlQW5kUmVnaXN0ZXJSZW1vdGVSZWFjdENvbXBvbmVudCgnU3RhdGlzdGljc1RyZW5kJyk7XG4vKipcbiAqIFRoZSBgVGFibGVgIGNvbXBvbmVudCByZW5kZXJzIGEgdGFibGUuIFRvIGZvcm1hdCB0aGUgdGFibGUsIHVzZSB0aGUgc3ViY29tcG9uZW50cyBgVGFibGVIZWFkYCwgYFRhYmxlUm93YCwgYFRhYmxlSGVhZGVyYCwgYFRhYmxlQm9keWAsIGBUYWJsZUNlbGxgYW5kIGBUYWJsZUZvb3RlcmAuXG4gKlxuICogKipMaW5rczoqKlxuICpcbiAqIC0ge0BsaW5rIGh0dHBzOi8vZGV2ZWxvcGVycy5odWJzcG90LmNvbS9kb2NzL3JlZmVyZW5jZS91aS1jb21wb25lbnRzL3N0YW5kYXJkLWNvbXBvbmVudHMvdGFibGUgRG9jc31cbiAqIC0ge0BsaW5rIGh0dHBzOi8vZ2l0aHViLmNvbS9IdWJTcG90L3VpLWV4dGVuc2lvbnMtZXhhbXBsZXMvdHJlZS9tYWluL2Rlc2lnbi1wYXR0ZXJucyN0YWJsZSBEZXNpZ24gUGF0dGVybiBFeGFtcGxlfVxuICovXG5leHBvcnQgY29uc3QgVGFibGUgPSBjcmVhdGVBbmRSZWdpc3RlclJlbW90ZVJlYWN0Q29tcG9uZW50KCdUYWJsZScpO1xuLyoqXG4gKiBUaGUgYFRhYmxlRm9vdGVyYCBjb21wb25lbnQgcmVuZGVycyBhIGZvb3RlciB3aXRoaW4gYSBgVGFibGVgIGNvbXBvbmVudC4gVXNlIHRoaXMgY29tcG9uZW50IHRvIGRpc3BsYXkgdG90YWxzIG9yIG90aGVyIHN1bW1hcnkgaW5mb3JtYXRpb24uXG4gKlxuICogKipMaW5rczoqKlxuICpcbiAqIC0ge0BsaW5rIGh0dHBzOi8vZGV2ZWxvcGVycy5odWJzcG90LmNvbS9kb2NzL3JlZmVyZW5jZS91aS1jb21wb25lbnRzL3N0YW5kYXJkLWNvbXBvbmVudHMvdGFibGUgRG9jc31cbiAqL1xuZXhwb3J0IGNvbnN0IFRhYmxlRm9vdGVyID0gY3JlYXRlQW5kUmVnaXN0ZXJSZW1vdGVSZWFjdENvbXBvbmVudCgnVGFibGVGb290ZXInKTtcbi8qKlxuICogVGhlIGBUYWJsZUNlbGxgIGNvbXBvbmVudCByZW5kZXJzIGluZGl2aWR1YWwgY2VsbHMgd2l0aGluIHRoZSBgVGFibGVCb2R5YCBjb21wb25lbnQuXG4gKlxuICogKipMaW5rczoqKlxuICpcbiAqIC0ge0BsaW5rIGh0dHBzOi8vZGV2ZWxvcGVycy5odWJzcG90LmNvbS9kb2NzL3JlZmVyZW5jZS91aS1jb21wb25lbnRzL3N0YW5kYXJkLWNvbXBvbmVudHMvdGFibGUgRG9jc31cbiAqL1xuZXhwb3J0IGNvbnN0IFRhYmxlQ2VsbCA9IGNyZWF0ZUFuZFJlZ2lzdGVyUmVtb3RlUmVhY3RDb21wb25lbnQoJ1RhYmxlQ2VsbCcpO1xuLyoqXG4gKiBUaGUgYFRhYmxlUm93YCBjb21wb25lbnQgcmVuZGVycyBhIHJvdyB3aXRoaW4gdGhlIGBUYWJsZUJvZHlgIG9yIGBUYWJsZUhlYWRgIGNvbXBvbmVudC5cbiAqXG4gKiAqKkxpbmtzOioqXG4gKlxuICogLSB7QGxpbmsgaHR0cHM6Ly9kZXZlbG9wZXJzLmh1YnNwb3QuY29tL2RvY3MvcmVmZXJlbmNlL3VpLWNvbXBvbmVudHMvc3RhbmRhcmQtY29tcG9uZW50cy90YWJsZSBEb2NzfVxuICovXG5leHBvcnQgY29uc3QgVGFibGVSb3cgPSBjcmVhdGVBbmRSZWdpc3RlclJlbW90ZVJlYWN0Q29tcG9uZW50KCdUYWJsZVJvdycpO1xuLyoqXG4gKiBUaGUgYFRhYmxlQm9keWAgY29tcG9uZW50IHJlbmRlcnMgdGhlIGJvZHkgKHJvd3MgYW5kIGNlbGxzKSBvZiBhIHRhYmxlIHdpdGhpbiB0aGUgYFRhYmxlYCBjb21wb25lbnQuXG4gKlxuICogKipMaW5rczoqKlxuICpcbiAqIC0ge0BsaW5rIGh0dHBzOi8vZGV2ZWxvcGVycy5odWJzcG90LmNvbS9kb2NzL3JlZmVyZW5jZS91aS1jb21wb25lbnRzL3N0YW5kYXJkLWNvbXBvbmVudHMvdGFibGUgRG9jc31cbiAqL1xuZXhwb3J0IGNvbnN0IFRhYmxlQm9keSA9IGNyZWF0ZUFuZFJlZ2lzdGVyUmVtb3RlUmVhY3RDb21wb25lbnQoJ1RhYmxlQm9keScpO1xuLyoqXG4gKiBUaGUgYFRhYmxlSGVhZGVyYCBjb21wb25lbnQgcmVuZGVycyBpbmRpdmlkdWFsIGNlbGxzIGNvbnRhaW5pbmcgYm9sZGVkIGNvbHVtbiBsYWJlbHMsIHdpdGhpbiBgVGFibGVIZWFkYC5cbiAqXG4gKiAqKkxpbmtzOioqXG4gKlxuICogLSB7QGxpbmsgaHR0cHM6Ly9kZXZlbG9wZXJzLmh1YnNwb3QuY29tL2RvY3MvcmVmZXJlbmNlL3VpLWNvbXBvbmVudHMvc3RhbmRhcmQtY29tcG9uZW50cy90YWJsZSBEb2NzfVxuICovXG5leHBvcnQgY29uc3QgVGFibGVIZWFkZXIgPSBjcmVhdGVBbmRSZWdpc3RlclJlbW90ZVJlYWN0Q29tcG9uZW50KCdUYWJsZUhlYWRlcicpO1xuLyoqXG4gKiBUaGUgYFRhYmxlSGVhZGAgY29tcG9uZW50IHJlbmRlcnMgdGhlIGhlYWRlciBzZWN0aW9uIG9mIHRoZSBgVGFibGVgIGNvbXBvbmVudCwgY29udGFpbmluZyBjb2x1bW4gbGFiZWxzLlxuICpcbiAqICoqTGlua3M6KipcbiAqXG4gKiAtIHtAbGluayBodHRwczovL2RldmVsb3BlcnMuaHVic3BvdC5jb20vZG9jcy9yZWZlcmVuY2UvdWktY29tcG9uZW50cy9zdGFuZGFyZC1jb21wb25lbnRzL3RhYmxlIERvY3N9XG4gKi9cbmV4cG9ydCBjb25zdCBUYWJsZUhlYWQgPSBjcmVhdGVBbmRSZWdpc3RlclJlbW90ZVJlYWN0Q29tcG9uZW50KCdUYWJsZUhlYWQnKTtcbi8qKlxuICogVGhlIGBOdW1iZXJJbnB1dGAgY29tcG9uZW50IHJlbmRlcnMgYSBudW1iZXIgaW5wdXQgZmllbGQuIExpa2Ugb3RoZXIgaW5wdXRzLCB0aGlzIGNvbXBvbmVudCBzaG91bGQgYmUgdXNlZCB3aXRoaW4gYSBgRm9ybWAgdGhhdCBoYXMgYSBzdWJtaXQgYnV0dG9uLlxuICpcbiAqICoqTGlua3M6KipcbiAqXG4gKiAtIHtAbGluayBodHRwczovL2RldmVsb3BlcnMuaHVic3BvdC5jb20vZG9jcy9yZWZlcmVuY2UvdWktY29tcG9uZW50cy9zdGFuZGFyZC1jb21wb25lbnRzL251bWJlci1pbnB1dCBEb2NzfVxuICovXG5leHBvcnQgY29uc3QgTnVtYmVySW5wdXQgPSBjcmVhdGVBbmRSZWdpc3RlclJlbW90ZVJlYWN0Q29tcG9uZW50KCdOdW1iZXJJbnB1dCcpO1xuLyoqXG4gKiBUaGUgYEJveGAgY29tcG9uZW50IHJlbmRlcnMgYW4gZW1wdHkgZGl2IGNvbnRhaW5lciBmb3IgZmluZSB0dW5pbmcgdGhlIHNwYWNpbmcgb2YgY29tcG9uZW50cy4gQ29tbW9ubHkgdXNlZCB3aXRoIHRoZSBgRmxleGAgY29tcG9uZW50LlxuICpcbiAqICoqTGlua3M6KipcbiAqXG4gKiAtIHtAbGluayBodHRwczovL2RldmVsb3BlcnMuaHVic3BvdC5jb20vZG9jcy9yZWZlcmVuY2UvdWktY29tcG9uZW50cy9zdGFuZGFyZC1jb21wb25lbnRzL2JveCBEb2NzfVxuICogLSB7QGxpbmsgaHR0cHM6Ly9naXRodWIuY29tL0h1YlNwb3QvdWktZXh0ZW5zaW9ucy1leGFtcGxlcy90cmVlL21haW4vZmxleC1hbmQtYm94IEZsZXggYW5kIEJveCBFeGFtcGxlfVxuICovXG5leHBvcnQgY29uc3QgQm94ID0gY3JlYXRlQW5kUmVnaXN0ZXJSZW1vdGVSZWFjdENvbXBvbmVudCgnQm94Jyk7XG4vKipcbiAqIFRoZSBgU3RlcEluZGljYXRvcmAgY29tcG9uZW50IHJlbmRlcnMgYW4gaW5kaWNhdG9yIHRvIHNob3cgdGhlIGN1cnJlbnQgc3RlcCBvZiBhIG11bHRpLXN0ZXAgcHJvY2Vzcy5cbiAqXG4gKiAqKkxpbmtzOioqXG4gKlxuICogLSB7QGxpbmsgaHR0cHM6Ly9kZXZlbG9wZXJzLmh1YnNwb3QuY29tL2RvY3MvcmVmZXJlbmNlL3VpLWNvbXBvbmVudHMvc3RhbmRhcmQtY29tcG9uZW50cy9zdGVwLWluZGljYXRvciBEb2NzfVxuICovXG5leHBvcnQgY29uc3QgU3RlcEluZGljYXRvciA9IGNyZWF0ZUFuZFJlZ2lzdGVyUmVtb3RlUmVhY3RDb21wb25lbnQoJ1N0ZXBJbmRpY2F0b3InKTtcbi8qKlxuICogVGhlIGBBY2NvcmRpb25gIGNvbXBvbmVudCByZW5kZXJzIGFuIGV4cGFuZGFibGUgYW5kIGNvbGxhcHNhYmxlIHNlY3Rpb24gdGhhdCBjYW4gY29udGFpbiBvdGhlciBjb21wb25lbnRzLiBUaGlzIGNvbXBvbmVudCBjYW4gYmUgaGVscGZ1bCBmb3Igc2F2aW5nIHNwYWNlIGFuZCBicmVha2luZyB1cCBleHRlbnNpb24gY29udGVudC5cbiAqXG4gKiAqKkxpbmtzOioqXG4gKlxuICogLSB7QGxpbmsgaHR0cHM6Ly9kZXZlbG9wZXJzLmh1YnNwb3QuY29tL2RvY3MvcmVmZXJlbmNlL3VpLWNvbXBvbmVudHMvc3RhbmRhcmQtY29tcG9uZW50cy9hY2NvcmRpb24gRG9jc31cbiAqL1xuZXhwb3J0IGNvbnN0IEFjY29yZGlvbiA9IGNyZWF0ZUFuZFJlZ2lzdGVyUmVtb3RlUmVhY3RDb21wb25lbnQoJ0FjY29yZGlvbicpO1xuLyoqXG4gKiBUaGUgTXVsdGlTZWxlY3QgY29tcG9uZW50IHJlbmRlcnMgYSBkcm9wZG93biBtZW51IHNlbGVjdCBmaWVsZCB3aGVyZSBhIHVzZXIgY2FuIHNlbGVjdCBtdWx0aXBsZSB2YWx1ZXMuIENvbW1vbmx5IHVzZWQgd2l0aGluIHRoZSBgRm9ybWAgY29tcG9uZW50LlxuICpcbiAqICoqTGlua3M6KipcbiAqXG4gKiAtIHtAbGluayBodHRwczovL2RldmVsb3BlcnMuaHVic3BvdC5jb20vZG9jcy9yZWZlcmVuY2UvdWktY29tcG9uZW50cy9zdGFuZGFyZC1jb21wb25lbnRzL211bHRpLXNlbGVjdCBEb2NzfVxuICovXG5leHBvcnQgY29uc3QgTXVsdGlTZWxlY3QgPSBjcmVhdGVBbmRSZWdpc3RlclJlbW90ZVJlYWN0Q29tcG9uZW50KCdNdWx0aVNlbGVjdCcpO1xuLyoqXG4gKiBUaGUgYEZsZXhgIGNvbXBvbmVudCByZW5kZXJzIGEgZmxleCBjb250YWluZXIgdGhhdCBjYW4gY29udGFpbiBvdGhlciBjb21wb25lbnRzLCBhbmQgYXJyYW5nZSB0aGVtIHdpdGggcHJvcHMuIFVzZSB0aGlzIGNvbXBvbmVudCB0byBjcmVhdGUgYSBmbGV4aWJsZSBhbmQgcmVzcG9uc2l2ZSBsYXlvdXQuXG4gKlxuICogKipMaW5rczoqKlxuICpcbiAqIC0ge0BsaW5rIGh0dHBzOi8vZGV2ZWxvcGVycy5odWJzcG90LmNvbS9kb2NzL3JlZmVyZW5jZS91aS1jb21wb25lbnRzL3N0YW5kYXJkLWNvbXBvbmVudHMvZmxleCBEb2NzfVxuICogLSB7QGxpbmsgaHR0cHM6Ly9naXRodWIuY29tL0h1YlNwb3QvdWktZXh0ZW5zaW9ucy1leGFtcGxlcy90cmVlL21haW4vZmxleC1hbmQtYm94IEZsZXggYW5kIEJveCBFeGFtcGxlfVxuICovXG5leHBvcnQgY29uc3QgRmxleCA9IGNyZWF0ZUFuZFJlZ2lzdGVyUmVtb3RlUmVhY3RDb21wb25lbnQoJ0ZsZXgnKTtcbi8qKlxuICogVGhlIGBEYXRlSW5wdXRgIGNvbXBvbmVudCByZW5kZXJzIGFuIGlucHV0IGZpZWxkIHdoZXJlIGEgdXNlciBjYW4gc2VsZWN0IGEgZGF0ZS4gQ29tbW9ubHkgdXNlZCB3aXRoaW4gdGhlIGBGb3JtYCBjb21wb25lbnQuXG4gKlxuICogKipMaW5rczoqKlxuICpcbiAqIC0ge0BsaW5rIGh0dHBzOi8vZGV2ZWxvcGVycy5odWJzcG90LmNvbS9kb2NzL3JlZmVyZW5jZS91aS1jb21wb25lbnRzL3N0YW5kYXJkLWNvbXBvbmVudHMvZGF0ZS1pbnB1dCBEb2NzfVxuICovXG5leHBvcnQgY29uc3QgRGF0ZUlucHV0ID0gY3JlYXRlQW5kUmVnaXN0ZXJSZW1vdGVSZWFjdENvbXBvbmVudCgnRGF0ZUlucHV0Jyk7XG4vKipcbiAqIFRoZSBgQ2hlY2tib3hgIGNvbXBvbmVudCByZW5kZXJzIGEgc2luZ2xlIGNoZWNrYm94IGlucHV0LiBDb21tb25seSB1c2VkIHdpdGhpbiB0aGUgYEZvcm1gIGNvbXBvbmVudC4gSWYgeW91IHdhbnQgdG8gZGlzcGxheSBtdWx0aXBsZSBjaGVja2JveGVzLCB5b3Ugc2hvdWxkIHVzZSBgVG9nZ2xlR3JvdXBgIGluc3RlYWQsIGFzIGl0IGNvbWVzIHdpdGggZXh0cmEgbG9naWMgZm9yIGhhbmRsaW5nIG11bHRpcGxlIGNoZWNrYm94ZXMuXG4gKlxuICogKipMaW5rczoqKlxuICpcbiAqIC0ge0BsaW5rIGh0dHBzOi8vZGV2ZWxvcGVycy5odWJzcG90LmNvbS9kb2NzL3JlZmVyZW5jZS91aS1jb21wb25lbnRzL3N0YW5kYXJkLWNvbXBvbmVudHMvY2hlY2tib3ggRG9jc31cbiAqL1xuZXhwb3J0IGNvbnN0IENoZWNrYm94ID0gY3JlYXRlQW5kUmVnaXN0ZXJSZW1vdGVSZWFjdENvbXBvbmVudCgnQ2hlY2tib3gnKTtcbi8qKlxuICogVGhlIGBSYWRpb0J1dHRvbmAgY29tcG9uZW50IHJlbmRlcnMgYSBzaW5nbGUgcmFkaW8gaW5wdXQuIENvbW1vbmx5IHVzZWQgd2l0aGluIHRoZSBgRm9ybWAgY29tcG9uZW50LiBJZiB5b3Ugd2FudCB0byBkaXNwbGF5IG11bHRpcGxlIHJhZGlvIGlucHV0cywgeW91IHNob3VsZCB1c2UgYFRvZ2dsZUdyb3VwYCBpbnN0ZWFkLCBhcyBpdCBjb21lcyB3aXRoIGV4dHJhIGxvZ2ljIGZvciBoYW5kbGluZyBtdWx0aXBsZSBpbnB1dHMuXG4gKi9cbmV4cG9ydCBjb25zdCBSYWRpb0J1dHRvbiA9IGNyZWF0ZUFuZFJlZ2lzdGVyUmVtb3RlUmVhY3RDb21wb25lbnQoJ1JhZGlvQnV0dG9uJyk7XG4vKipcbiAqIFRoZSBgTGlzdGAgY29tcG9uZW50IHJlbmRlcnMgYSBsaXN0IG9mIGl0ZW1zLiBVc2UgdGhpcyBjb21wb25lbnQgdG8gZGlzcGxheSBhIGxpc3Qgb2YgaXRlbXMsIHN1Y2ggYXMgYSBsaXN0IG9mIGNvbnRhY3RzLCB0YXNrcywgb3Igb3RoZXIgZGF0YS4gQSBsaXN0IGNhbiBiZSBzdHlsZWQgYXMgYSBidWxsZXRlZCBsaXN0IG9yIGEgbnVtYmVyZWQgbGlzdC5cbiAqXG4gKiAqKkxpbmtzOioqXG4gKlxuICogLSB7QGxpbmsgaHR0cHM6Ly9kZXZlbG9wZXJzLmh1YnNwb3QuY29tL2RvY3MvcmVmZXJlbmNlL3VpLWNvbXBvbmVudHMvc3RhbmRhcmQtY29tcG9uZW50cy9saXN0IERvY3N9XG4gKi9cbmV4cG9ydCBjb25zdCBMaXN0ID0gY3JlYXRlQW5kUmVnaXN0ZXJSZW1vdGVSZWFjdENvbXBvbmVudCgnTGlzdCcpO1xuLyoqXG4gKiBUaGUgYFRvZ2dsZWAgY29tcG9uZW50IHJlbmRlcnMgYSBib29sZWFuIHRvZ2dsZSBzd2l0Y2ggdGhhdCBjYW4gYmUgY29uZmlndXJlZCB3aXRoIHNpemluZywgbGFiZWwgcG9zaXRpb24sIHJlYWQtb25seSwgYW5kIG1vcmUuXG4gKlxuICogKipMaW5rczoqKlxuICpcbiAqIC0ge0BsaW5rIGh0dHBzOi8vZGV2ZWxvcGVycy5odWJzcG90LmNvbS9kb2NzL3JlZmVyZW5jZS91aS1jb21wb25lbnRzL3N0YW5kYXJkLWNvbXBvbmVudHMvdG9nZ2xlIERvY3N9XG4gKi9cbmV4cG9ydCBjb25zdCBUb2dnbGUgPSBjcmVhdGVBbmRSZWdpc3RlclJlbW90ZVJlYWN0Q29tcG9uZW50KCdUb2dnbGUnKTtcbi8qKlxuICogVGhlIGBEcm9wZG93bmAgY29tcG9uZW50IHJlbmRlcnMgYSBkcm9wZG93biBtZW51IHRoYXQgY2FuIGFwcGVhciBhcyBhIGJ1dHRvbiBvciBoeXBlcmxpbmsuIFVzZSB0aGlzIGNvbXBvbmVudCB0byBlbmFibGUgdXNlcnMgdG8gc2VsZWN0IGZyb20gbXVsdGlwbGUgb3B0aW9ucyBpbiBhIGNvbXBhY3QgbGlzdC5cbiAqXG4gKiAqKkxpbmtzOioqXG4gKlxuICogLSB7QGxpbmsgaHR0cHM6Ly9kZXZlbG9wZXJzLmh1YnNwb3QuY29tL2RvY3MvcmVmZXJlbmNlL3VpLWNvbXBvbmVudHMvc3RhbmRhcmQtY29tcG9uZW50cy9kcm9wZG93biBEb2NzfVxuICovXG5leHBvcnQgY29uc3QgRHJvcGRvd24gPSBjcmVhdGVBbmRSZWdpc3RlclJlbW90ZUNvbXBvdW5kUmVhY3RDb21wb25lbnQoJ0Ryb3Bkb3duJywge1xuICAgIGNvbXBvdW5kQ29tcG9uZW50UHJvcGVydGllczoge1xuICAgICAgICAvKipcbiAgICAgICAgICogVGhlIGBEcm9wZG93bi5CdXR0b25JdGVtYCBjb21wb25lbnQgcmVwcmVzZW50cyBhIHNpbmdsZSBvcHRpb24gd2l0aGluIGEgYERyb3Bkb3duYCBtZW51LiBVc2UgdGhpcyBjb21wb25lbnQgYXMgYSBjaGlsZCBvZiB0aGUgYERyb3Bkb3duYCBjb21wb25lbnQuXG4gICAgICAgICAqXG4gICAgICAgICAqICoqTGlua3M6KipcbiAgICAgICAgICpcbiAgICAgICAgICogLSB7QGxpbmsgaHR0cHM6Ly9kZXZlbG9wZXJzLmh1YnNwb3QuY29tL2RvY3MvcmVmZXJlbmNlL3VpLWNvbXBvbmVudHMvc3RhbmRhcmQtY29tcG9uZW50cy9kcm9wZG93biBEb2NzfVxuICAgICAgICAgKi9cbiAgICAgICAgQnV0dG9uSXRlbTogY3JlYXRlQW5kUmVnaXN0ZXJSZW1vdGVSZWFjdENvbXBvbmVudCgnRHJvcGRvd25CdXR0b25JdGVtJywge1xuICAgICAgICAgICAgZnJhZ21lbnRQcm9wczogWydvdmVybGF5J10sXG4gICAgICAgIH0pLFxuICAgIH0sXG59KTtcbi8qKlxuICogVGhlIFBhbmVsIGNvbXBvbmVudCByZW5kZXJzIGEgcGFuZWwgb3ZlcmxheSBvbiB0aGUgcmlnaHQgc2lkZSBvZiB0aGUgcGFnZSBhbmQgY29udGFpbnMgb3RoZXIgY29tcG9uZW50cy5cbiAqXG4gKiAqKkxpbmtzOioqXG4gKlxuICogLSB7QGxpbmsgaHR0cHM6Ly9kZXZlbG9wZXJzLmh1YnNwb3QuY29tL2RvY3MvcmVmZXJlbmNlL3VpLWNvbXBvbmVudHMvc3RhbmRhcmQtY29tcG9uZW50cy9wYW5lbCBEb2NzfVxuICogLSB7QGxpbmsgaHR0cHM6Ly9naXRodWIuY29tL0h1YlNwb3QvdWktZXh0ZW5zaW9ucy1leGFtcGxlcy90cmVlL21haW4vb3ZlcmxheS1leGFtcGxlIE92ZXJsYXkgRXhhbXBsZX1cbiAqIC0ge0BsaW5rIGh0dHBzOi8vZ2l0aHViLmNvbS9IdWJTcG90L3VpLWV4dGVuc2lvbnMtZXhhbXBsZXMvdHJlZS9tYWluL2Rlc2lnbi1wYXR0ZXJucyNwYW5lbCBEZXNpZ24gUGF0dGVybiBFeGFtcGxlc31cbiAqL1xuZXhwb3J0IGNvbnN0IFBhbmVsID0gY3JlYXRlQW5kUmVnaXN0ZXJSZW1vdGVSZWFjdENvbXBvbmVudCgnUGFuZWwnKTtcbi8qKlxuICogVGhlIGBQYW5lbEZvb3RlcmAgaXMgYSBzdGlja3kgZm9vdGVyIGNvbXBvbmVudCBkaXNwbGF5ZWQgYXQgdGhlIGJvdHRvbSBvZiBhIGBQYW5lbGAgY29tcG9uZW50LiBVc2UgdGhpcyBjb21wb25lbnQgdG8gZGlzcGxheSBhY3Rpb25zIG9yIG90aGVyIGNvbnRlbnQgdGhhdCBzaG91bGQgYmUgdmlzaWJsZSBhdCBhbGwgdGltZXMuIEluY2x1ZGUgb25seSBvbmUgYFBhbmVsRm9vdGVyYCBjb21wb25lbnQgcGVyIGBQYW5lbGAuXG4gKlxuICogKipMaW5rczoqKlxuICpcbiAqIC0ge0BsaW5rIGh0dHBzOi8vZGV2ZWxvcGVycy5odWJzcG90LmNvbS9kb2NzL3JlZmVyZW5jZS91aS1jb21wb25lbnRzL3N0YW5kYXJkLWNvbXBvbmVudHMvcGFuZWwtZm9vdGVyIERvY3N9XG4gKiAtIHtAbGluayBodHRwczovL2dpdGh1Yi5jb20vSHViU3BvdC91aS1leHRlbnNpb25zLWV4YW1wbGVzL3RyZWUvbWFpbi9vdmVybGF5LWV4YW1wbGUgT3ZlcmxheSBFeGFtcGxlfVxuICovXG5leHBvcnQgY29uc3QgUGFuZWxGb290ZXIgPSBjcmVhdGVBbmRSZWdpc3RlclJlbW90ZVJlYWN0Q29tcG9uZW50KCdQYW5lbEZvb3RlcicpO1xuLyoqXG4gKiBUaGUgYFBhbmVsQm9keWAgY29tcG9uZW50IGlzIGEgY29udGFpbmVyIHRoYXQgd3JhcHMgdGhlIHBhbmVsJ3MgY29udGVudCBhbmQgbWFrZXMgaXQgc2Nyb2xsYWJsZS4gSW5jbHVkZSBvbmx5IG9uZSBgUGFuZWxCb2R5YCBjb21wb25lbnQgcGVyIGBQYW5lbGAuXG4gKlxuICogKipMaW5rczoqKlxuICpcbiAqIC0ge0BsaW5rIGh0dHBzOi8vZGV2ZWxvcGVycy5odWJzcG90LmNvbS9kb2NzL3JlZmVyZW5jZS91aS1jb21wb25lbnRzL3N0YW5kYXJkLWNvbXBvbmVudHMvcGFuZWwtZm9vdGVyIERvY3N9XG4gKiAtIHtAbGluayBodHRwczovL2dpdGh1Yi5jb20vSHViU3BvdC91aS1leHRlbnNpb25zLWV4YW1wbGVzL3RyZWUvbWFpbi9vdmVybGF5LWV4YW1wbGUgT3ZlcmxheSBFeGFtcGxlfVxuICovXG5leHBvcnQgY29uc3QgUGFuZWxCb2R5ID0gY3JlYXRlQW5kUmVnaXN0ZXJSZW1vdGVSZWFjdENvbXBvbmVudCgnUGFuZWxCb2R5Jyk7XG4vKipcbiAqIFRoZSBgUGFuZWxTZWN0aW9uYCBjb21wb25lbnQgaXMgYSBjb250YWluZXIgdGhhdCBhZGRzIHBhZGRpbmcgYW5kIGJvdHRvbSBtYXJnaW4gdG8gcHJvdmlkZSBzcGFjaW5nIGJldHdlZW4gY29udGVudC4gVXNlIHRoZSBgUGFuZWxTZWN0aW9uYCBjb21wb25lbnQgdG8gc2VwYXJhdGUgY29udGVudCB3aXRoaW4gYSBgUGFuZWxCb2R5YC5cbiAqXG4gKiAqKkxpbmtzOioqXG4gKlxuICogLSB7QGxpbmsgaHR0cHM6Ly9kZXZlbG9wZXJzLmh1YnNwb3QuY29tL2RvY3MvcmVmZXJlbmNlL3VpLWNvbXBvbmVudHMvc3RhbmRhcmQtY29tcG9uZW50cy9wYW5lbC1mb290ZXIgRG9jc31cbiAqIC0ge0BsaW5rIGh0dHBzOi8vZ2l0aHViLmNvbS9IdWJTcG90L3VpLWV4dGVuc2lvbnMtZXhhbXBsZXMvdHJlZS9tYWluL292ZXJsYXktZXhhbXBsZSBPdmVybGF5IEV4YW1wbGV9XG4gKi9cbmV4cG9ydCBjb25zdCBQYW5lbFNlY3Rpb24gPSBjcmVhdGVBbmRSZWdpc3RlclJlbW90ZVJlYWN0Q29tcG9uZW50KCdQYW5lbFNlY3Rpb24nKTtcbi8qKlxuICogVGhlIGBTdGVwcGVySW5wdXRgIGNvbXBvbmVudCByZW5kZXJzIGEgbnVtYmVyIGlucHV0IGZpZWxkIHRoYXQgY2FuIGJlIGluY3JlYXNlZCBvciBkZWNyZWFzZWQgYnkgYSBzZXQgbnVtYmVyLiBDb21tb25seSB1c2VkIHdpdGhpbiB0aGUgYEZvcm1gIGNvbXBvbmVudC5cbiAqXG4gKiAqKkxpbmtzOioqXG4gKlxuICogLSB7QGxpbmsgaHR0cHM6Ly9kZXZlbG9wZXJzLmh1YnNwb3QuY29tL2RvY3MvcmVmZXJlbmNlL3VpLWNvbXBvbmVudHMvc3RhbmRhcmQtY29tcG9uZW50cy9zdGVwcGVyLWlucHV0IERvY3N9XG4gKi9cbmV4cG9ydCBjb25zdCBTdGVwcGVySW5wdXQgPSBjcmVhdGVBbmRSZWdpc3RlclJlbW90ZVJlYWN0Q29tcG9uZW50KCdTdGVwcGVySW5wdXQnKTtcbi8qKlxuICogVGhlIE1vZGFsIGNvbXBvbmVudCByZW5kZXJzIGEgcG9wLXVwIG92ZXJsYXkgdGhhdCBjYW4gY29udGFpbiBvdGhlciBjb21wb25lbnRzLlxuICpcbiAqICoqTGlua3M6KipcbiAqXG4gKiAtIHtAbGluayBodHRwczovL2RldmVsb3BlcnMuaHVic3BvdC5jb20vZG9jcy9yZWZlcmVuY2UvdWktY29tcG9uZW50cy9zdGFuZGFyZC1jb21wb25lbnRzL21vZGFsIERvY3N9XG4gKiAtIHtAbGluayBodHRwczovL2dpdGh1Yi5jb20vSHViU3BvdC91aS1leHRlbnNpb25zLWV4YW1wbGVzL3RyZWUvbWFpbi9vdmVybGF5LWV4YW1wbGUgT3ZlcmxheSBFeGFtcGxlfVxuICogLSB7QGxpbmsgaHR0cHM6Ly9naXRodWIuY29tL0h1YlNwb3QvdWktZXh0ZW5zaW9ucy1leGFtcGxlcy90cmVlL21haW4vZGVzaWduLXBhdHRlcm5zI21vZGFsIERlc2lnbiBQYXR0ZXJuIEV4YW1wbGVzfVxuICovXG5leHBvcnQgY29uc3QgTW9kYWwgPSBjcmVhdGVBbmRSZWdpc3RlclJlbW90ZVJlYWN0Q29tcG9uZW50KCdNb2RhbCcpO1xuLyoqXG4gKiBUaGUgYE1vZGFsQm9keWAgY29tcG9uZW50IGNvbnRhaW5zIHRoZSBtYWluIGNvbnRlbnQgb2YgdGhlIG1vZGFsLiBPbmUgYE1vZGFsQm9keWAgaXMgcmVxdWlyZWQgcGVyIGBNb2RhbGAuXG4gKlxuICogKipMaW5rczoqKlxuICpcbiAqIC0ge0BsaW5rIGh0dHBzOi8vZGV2ZWxvcGVycy5odWJzcG90LmNvbS9kb2NzL3JlZmVyZW5jZS91aS1jb21wb25lbnRzL3N0YW5kYXJkLWNvbXBvbmVudHMvbW9kYWwgRG9jc31cbiAqIC0ge0BsaW5rIGh0dHBzOi8vZ2l0aHViLmNvbS9IdWJTcG90L3VpLWV4dGVuc2lvbnMtZXhhbXBsZXMvdHJlZS9tYWluL292ZXJsYXktZXhhbXBsZSBPdmVybGF5IEV4YW1wbGV9XG4gKi9cbmV4cG9ydCBjb25zdCBNb2RhbEJvZHkgPSBjcmVhdGVBbmRSZWdpc3RlclJlbW90ZVJlYWN0Q29tcG9uZW50KCdNb2RhbEJvZHknKTtcbi8qKlxuICogVGhlIGBNb2RhbEZvb3RlcmAgY29tcG9uZW50IGlzIGFuIG9wdGlvbmFsIGNvbXBvbmVudCB0byBmb3JtYXQgdGhlIGZvb3RlciBzZWN0aW9uIG9mIHRoZSBtb2RhbC4gVXNlIG9uZSBgTW9kYWxGb290ZXJgIHBlciBgTW9kYWxgLlxuICpcbiAqICoqTGlua3M6KipcbiAqXG4gKiAtIHtAbGluayBodHRwczovL2RldmVsb3BlcnMuaHVic3BvdC5jb20vZG9jcy9yZWZlcmVuY2UvdWktY29tcG9uZW50cy9zdGFuZGFyZC1jb21wb25lbnRzL21vZGFsIERvY3N9XG4gKiAtIHtAbGluayBodHRwczovL2dpdGh1Yi5jb20vSHViU3BvdC91aS1leHRlbnNpb25zLWV4YW1wbGVzL3RyZWUvbWFpbi9vdmVybGF5LWV4YW1wbGUgT3ZlcmxheSBFeGFtcGxlfVxuICovXG5leHBvcnQgY29uc3QgTW9kYWxGb290ZXIgPSBjcmVhdGVBbmRSZWdpc3RlclJlbW90ZVJlYWN0Q29tcG9uZW50KCdNb2RhbEZvb3RlcicpO1xuLyoqXG4gKiBVc2UgdGhlIGBJY29uYCBjb21wb25lbnQgdG8gcmVuZGVyIGEgdmlzdWFsIGljb24gd2l0aGluIG90aGVyIGNvbXBvbmVudHMuIEl0IGNhbiBnZW5lcmFsbHkgYmUgdXNlZCBpbnNpZGUgbW9zdCBjb21wb25lbnRzLCBleGNsdWRpbmcgb25lcyB0aGF0IGRvbid0IHN1cHBvcnQgY2hpbGQgY29tcG9uZW50cy5cbiAqXG4gKiAqKkxpbmtzOioqXG4gKlxuICogLSB7QGxpbmsgaHR0cHM6Ly9kZXZlbG9wZXJzLmh1YnNwb3QuY29tL2RvY3MvcmVmZXJlbmNlL3VpLWNvbXBvbmVudHMvc3RhbmRhcmQtY29tcG9uZW50cy9pY29uIERvY3N9XG4gKi9cbmV4cG9ydCBjb25zdCBJY29uID0gY3JlYXRlQW5kUmVnaXN0ZXJSZW1vdGVSZWFjdENvbXBvbmVudCgnSWNvbicpO1xuLyoqXG4gKiBUaGUgYFN0YXR1c1RhZ2AgY29tcG9uZW50IHJlbmRlcnMgYSB2aXN1YWwgaW5kaWNhdG9yIHRvIGRpc3BsYXkgdGhlIGN1cnJlbnQgc3RhdHVzIG9mIGFuIGl0ZW0uIFN0YXR1cyB0YWdzIGNhbiBiZSBzdGF0aWMgb3IgY2xpY2thYmxlLlxuICpcbiAqICoqTGlua3M6KipcbiAqXG4gKiAtIHtAbGluayBodHRwczovL2RldmVsb3BlcnMuaHVic3BvdC5jb20vZG9jcy9yZWZlcmVuY2UvdWktY29tcG9uZW50cy9zdGFuZGFyZC1jb21wb25lbnRzL3N0YXR1cy10YWcgRG9jc31cbiAqIC0ge0BsaW5rIGh0dHBzOi8vZGV2ZWxvcGVycy5odWJzcG90LmNvbS9kb2NzL3JlZmVyZW5jZS91aS1jb21wb25lbnRzL3N0YW5kYXJkLWNvbXBvbmVudHMvc3RhdHVzLXRhZyN2YXJpYW50cyBWYXJpYW50c31cbiAqL1xuZXhwb3J0IGNvbnN0IFN0YXR1c1RhZyA9IGNyZWF0ZUFuZFJlZ2lzdGVyUmVtb3RlUmVhY3RDb21wb25lbnQoJ1N0YXR1c1RhZycpO1xuLyoqXG4gKiBUaGUgYExvYWRpbmdCdXR0b25gIGNvbXBvbmVudCByZW5kZXJzIGEgYnV0dG9uIHdpdGggbG9hZGluZyBzdGF0ZSBvcHRpb25zLlxuICpcbiAqICoqTGlua3M6KipcbiAqXG4gKiAtIHtAbGluayBodHRwczovL2RldmVsb3BlcnMuaHVic3BvdC5jb20vZG9jcy9yZWZlcmVuY2UvdWktY29tcG9uZW50cy9zdGFuZGFyZC1jb21wb25lbnRzL2xvYWRpbmctYnV0dG9uIERvY3N9XG4gKi9cbmV4cG9ydCBjb25zdCBMb2FkaW5nQnV0dG9uID0gY3JlYXRlQW5kUmVnaXN0ZXJSZW1vdGVSZWFjdENvbXBvbmVudCgnTG9hZGluZ0J1dHRvbicsIHtcbiAgICBmcmFnbWVudFByb3BzOiBbJ292ZXJsYXknXSxcbn0pO1xuLyoqXG4gKiBUaGUgYEJhckNoYXJ0YCBjb21wb25lbnQgcmVuZGVycyBhIGJhciBjaGFydCBmb3IgdmlzdWFsaXppbmcgZGF0YS4gVGhpcyB0eXBlIG9mIGNoYXJ0IGlzIGJlc3Qgc3VpdGVkIGZvciBjb21wYXJpbmcgY2F0ZWdvcmljYWwgZGF0YS5cbiAqXG4gKiAqKkxpbmtzOioqXG4gKlxuICogLSB7QGxpbmsgaHR0cHM6Ly9kZXZlbG9wZXJzLmh1YnNwb3QuY29tL2RvY3MvcmVmZXJlbmNlL3VpLWNvbXBvbmVudHMvc3RhbmRhcmQtY29tcG9uZW50cy9iYXItY2hhcnQgQmFyQ2hhcnQgRG9jc31cbiAqIC0ge0BsaW5rIGh0dHBzOi8vZGV2ZWxvcGVycy5odWJzcG90LmNvbS9kb2NzL3JlZmVyZW5jZS91aS1jb21wb25lbnRzL3N0YW5kYXJkLWNvbXBvbmVudHMvY2hhcnRzIENoYXJ0cyBEb2NzfVxuICogLSB7QGxpbmsgaHR0cHM6Ly9naXRodWIuY29tL0h1YlNwb3QvdWktZXh0ZW5zaW9ucy1leGFtcGxlcy90cmVlL21haW4vY2hhcnRzLWV4YW1wbGUgQ2hhcnRzIEV4YW1wbGV9XG4gKi9cbmV4cG9ydCBjb25zdCBCYXJDaGFydCA9IGNyZWF0ZUFuZFJlZ2lzdGVyUmVtb3RlUmVhY3RDb21wb25lbnQoJ0JhckNoYXJ0Jyk7XG4vKipcbiAqIFRoZSBgTGluZUNoYXJ0YCBjb21wb25lbnQgcmVuZGVycyBhIGxpbmUgY2hhcnQgZm9yIHZpc3VhbGl6aW5nIGRhdGEuIFRoaXMgdHlwZSBvZiBjaGFydCBpcyBiZXN0IHN1aXRlZCBmb3IgdGltZSBzZXJpZXMgcGxvdHMgb3IgdHJlbmQgZGF0YS5cbiAqXG4gKiAqKkxpbmtzOioqXG4gKlxuICogLSB7QGxpbmsgaHR0cHM6Ly9kZXZlbG9wZXJzLmh1YnNwb3QuY29tL2RvY3MvcmVmZXJlbmNlL3VpLWNvbXBvbmVudHMvc3RhbmRhcmQtY29tcG9uZW50cy9saW5lLWNoYXJ0IExpbmVDaGFydCBEb2NzfVxuICogLSB7QGxpbmsgaHR0cHM6Ly9kZXZlbG9wZXJzLmh1YnNwb3QuY29tL2RvY3MvcmVmZXJlbmNlL3VpLWNvbXBvbmVudHMvc3RhbmRhcmQtY29tcG9uZW50cy9jaGFydHMgQ2hhcnRzIERvY3N9XG4gKiAtIHtAbGluayBodHRwczovL2dpdGh1Yi5jb20vSHViU3BvdC91aS1leHRlbnNpb25zLWV4YW1wbGVzL3RyZWUvbWFpbi9jaGFydHMtZXhhbXBsZSBDaGFydHMgRXhhbXBsZX1cbiAqL1xuZXhwb3J0IGNvbnN0IExpbmVDaGFydCA9IGNyZWF0ZUFuZFJlZ2lzdGVyUmVtb3RlUmVhY3RDb21wb25lbnQoJ0xpbmVDaGFydCcpO1xuLyoqXG4gKiBUaGUgYFNjb3JlQ2lyY2xlYCBjb21wb25lbnQgZGlzcGxheXMgYSBzY29yZSB2YWx1ZSAoMC0xMDApIGFzIGEgY2lyY3VsYXIgcHJvZ3Jlc3MgaW5kaWNhdG9yIHdpdGggY29sb3ItY29kZWQgYmFuZHMuXG4gKiBTY29yZXMgYXJlIGNvbG9yLWNvZGVkOiAwLTMyIChhbGVydC9yZWQpLCAzMy02NSAod2FybmluZy95ZWxsb3cpLCA2Ni0xMDAgKHN1Y2Nlc3MvZ3JlZW4pLlxuICogQGV4YW1wbGVcbiAqIGBgYHRzeFxuICogICA8U2NvcmVDaXJjbGUgc2NvcmU9ezc1fSAvPlxuICogYGBgXG4gKi9cbmV4cG9ydCBjb25zdCBTY29yZUNpcmNsZSA9IGNyZWF0ZUFuZFJlZ2lzdGVyUmVtb3RlUmVhY3RDb21wb25lbnQoJ1Njb3JlQ2lyY2xlJyk7XG4vKipcbiAqIGBUYWJzYCBhbGxvdyB5b3UgdG8gZ3JvdXAgcmVsYXRlZCBjb250ZW50IGluIGEgY29tcGFjdCBzcGFjZSwgYWxsb3dpbmcgdXNlcnMgdG8gc3dpdGNoIGJldHdlZW4gdmlld3Mgd2l0aG91dCBsZWF2aW5nIHRoZSBwYWdlLlxuICogQGV4YW1wbGVcbiAqIGBgYHRzeFxuICogPFRhYnMgZGVmYXVsdFNlbGVjdGVkPVwiMVwiPlxuICogICA8VGFiIHRhYklkPVwiMVwiPkZpcnN0IHRhYiBjb250ZW50PC9UYWI+XG4gKiAgIDxUYWIgdGFiSWQ9XCIyXCI+U2Vjb25kIHRhYiBjb250ZW50PC9UYWI+XG4gKiA8L1RhYnM+XG4gKiBgYGBcbiAqXG4gKiAqKkxpbmtzOioqXG4gKiAtIHtAbGluayBodHRwczovL2RldmVsb3BlcnMuaHVic3BvdC5jb20vZG9jcy9yZWZlcmVuY2UvdWktY29tcG9uZW50cy9zdGFuZGFyZC1jb21wb25lbnRzL3RhYnMgRG9jdW1lbnRhdGlvbn1cbiAqIC0ge0BsaW5rIGh0dHBzOi8vZ2l0aHViLmNvbS9odWJzcG90ZGV2L3VpZS10YWJiZWQtcHJvZHVjdC1jYXJvdXNlbCBUYWJzIEV4YW1wbGV9XG4gKi9cbmV4cG9ydCBjb25zdCBUYWJzID0gY3JlYXRlQW5kUmVnaXN0ZXJSZW1vdGVSZWFjdENvbXBvbmVudCgnVGFicycpO1xuLyoqXG4gKiBFYWNoIGBUYWJgIHJlcHJlc2VudHMgYSBzaW5nbGUgdGFiIChvciBcInZpZXdcIikgd2l0aGluIHRoZSBwYXJlbnQgYFRhYnNgIGNvbXBvbmVudC5cbiAqIEBleGFtcGxlXG4gKiBgYGB0c3hcbiAqIDxUYWJzIGRlZmF1bHRTZWxlY3RlZD1cIjFcIj5cbiAqICAgPFRhYiB0YWJJZD1cIjFcIj5GaXJzdCB0YWIgY29udGVudDwvVGFiPlxuICogICA8VGFiIHRhYklkPVwiMlwiPlNlY29uZCB0YWIgY29udGVudDwvVGFiPlxuICogPC9UYWJzPlxuICogYGBgXG4gKlxuICogKipMaW5rczoqKlxuICogLSB7QGxpbmsgaHR0cHM6Ly9kZXZlbG9wZXJzLmh1YnNwb3QuY29tL2RvY3MvcmVmZXJlbmNlL3VpLWNvbXBvbmVudHMvc3RhbmRhcmQtY29tcG9uZW50cy90YWJzIERvY3VtZW50YXRpb259XG4gKiAtIHtAbGluayBodHRwczovL2dpdGh1Yi5jb20vaHVic3BvdGRldi91aWUtdGFiYmVkLXByb2R1Y3QtY2Fyb3VzZWwgVGFicyBFeGFtcGxlfVxuICovXG5leHBvcnQgY29uc3QgVGFiID0gY3JlYXRlQW5kUmVnaXN0ZXJSZW1vdGVSZWFjdENvbXBvbmVudCgnVGFiJyk7XG4vKipcbiAqIFRoZSBgSWxsdXN0cmF0aW9uYCBjb21wb25lbnQgcmVuZGVycyBhbiBpbGx1c3RyYXRpb24uXG4gKlxuICogKipMaW5rczoqKlxuICpcbiAqIC0ge0BsaW5rIGh0dHBzOi8vZGV2ZWxvcGVycy5odWJzcG90LmNvbS9kb2NzL3JlZmVyZW5jZS91aS1jb21wb25lbnRzL3N0YW5kYXJkLWNvbXBvbmVudHMvaWxsdXN0cmF0aW9uIElsbHVzdHJhdGlvbiBEb2NzfVxuICovXG5leHBvcnQgY29uc3QgSWxsdXN0cmF0aW9uID0gY3JlYXRlQW5kUmVnaXN0ZXJSZW1vdGVSZWFjdENvbXBvbmVudCgnSWxsdXN0cmF0aW9uJyk7XG4vKipcbiAqIFRoZSBgVG9vbHRpcGAgY29tcG9uZW50IHJlbmRlcnMgYSB0b29sdGlwIGZvciBhIGNvbXBvbmVudC5cbiAqXG4gKiAqKkxpbmtzOioqXG4gKiAtIHtAbGluayBodHRwczovL2RldmVsb3BlcnMuaHVic3BvdC5jb20vZG9jcy9yZWZlcmVuY2UvdWktY29tcG9uZW50cy9zdGFuZGFyZC1jb21wb25lbnRzL3Rvb2x0aXAgRG9jdW1lbnRhdGlvbn1cbiAqL1xuZXhwb3J0IGNvbnN0IFRvb2x0aXAgPSBjcmVhdGVBbmRSZWdpc3RlclJlbW90ZVJlYWN0Q29tcG9uZW50KCdUb29sdGlwJyk7XG4vKipcbiAqIFRoZSBgU2VhcmNoSW5wdXRgIGNvbXBvbmVudCByZW5kZXJzIGEgc2VhcmNoIGlucHV0IGZpZWxkLlxuICpcbiAqICoqTGlua3M6KipcbiAqXG4gKiAtIHtAbGluayBodHRwczovL2RldmVsb3BlcnMuaHVic3BvdC5jb20vZG9jcy9yZWZlcmVuY2UvdWktY29tcG9uZW50cy9zdGFuZGFyZC1jb21wb25lbnRzL3NlYXJjaC1pbnB1dCBTZWFyY2hJbnB1dCBEb2NzfVxuICovXG5leHBvcnQgY29uc3QgU2VhcmNoSW5wdXQgPSBjcmVhdGVBbmRSZWdpc3RlclJlbW90ZVJlYWN0Q29tcG9uZW50KCdTZWFyY2hJbnB1dCcpO1xuLyoqXG4gKiBUaGUgYFRpbWVJbnB1dGAgY29tcG9uZW50IHJlbmRlcnMgYW4gaW5wdXQgZmllbGQgd2hlcmUgYSB1c2VyIGNhbiBzZWxlY3QgYSB0aW1lLiBDb21tb25seSB1c2VkIHdpdGhpbiB0aGUgYEZvcm1gIGNvbXBvbmVudC5cbiAqXG4gKiAqKkxpbmtzOioqXG4gKlxuICogLSB7QGxpbmsgaHR0cHM6Ly9kZXZlbG9wZXJzLmh1YnNwb3QuY29tL2RvY3MvcmVmZXJlbmNlL3VpLWNvbXBvbmVudHMvc3RhbmRhcmQtY29tcG9uZW50cy90aW1lLWlucHV0IERvY3N9XG4gKi9cbmV4cG9ydCBjb25zdCBUaW1lSW5wdXQgPSBjcmVhdGVBbmRSZWdpc3RlclJlbW90ZVJlYWN0Q29tcG9uZW50KCdUaW1lSW5wdXQnKTtcbi8qKlxuICogVGhlIGBDdXJyZW5jeUlucHV0YCBjb21wb25lbnQgcmVuZGVycyBhIGN1cnJlbmN5IGlucHV0IGZpZWxkIHdpdGggcHJvcGVyIGZvcm1hdHRpbmcsXG4gKiBjdXJyZW5jeSBzeW1ib2xzLCBhbmQgbG9jYWxlLXNwZWNpZmljIGRpc3BsYXkgcGF0dGVybnMuIENvbW1vbmx5IHVzZWQgd2l0aGluIHRoZSBgRm9ybWAgY29tcG9uZW50LlxuICpcbiAqICoqTGlua3M6KipcbiAqXG4gKiAtIHtAbGluayBodHRwczovL2RldmVsb3BlcnMuaHVic3BvdC5jb20vZG9jcy9yZWZlcmVuY2UvdWktY29tcG9uZW50cy9zdGFuZGFyZC1jb21wb25lbnRzL2N1cnJlbmN5LWlucHV0IERvY3N9XG4gKi9cbmV4cG9ydCBjb25zdCBDdXJyZW5jeUlucHV0ID0gY3JlYXRlQW5kUmVnaXN0ZXJSZW1vdGVSZWFjdENvbXBvbmVudCgnQ3VycmVuY3lJbnB1dCcpO1xuLyoqXG4gKiBUaGUgYElubGluZWAgY29tcG9uZW50IHNwcmVhZHMgYWxpZ25zIGl0cyBjaGlsZHJlbiBob3Jpem9udGFsbHkgKGFsb25nIHRoZSB4LWF4aXMpLlxuICpcbiAqICoqTGlua3M6KipcbiAqXG4gKiAtIHtAbGluayBodHRwczovL2RldmVsb3BlcnMuaHVic3BvdC5jb20vZG9jcy9yZWZlcmVuY2UvdWktY29tcG9uZW50cy9zdGFuZGFyZC1jb21wb25lbnRzL2lubGluZSBEb2NzfVxuICovIGV4cG9ydCBjb25zdCBJbmxpbmUgPSBjcmVhdGVBbmRSZWdpc3RlclJlbW90ZVJlYWN0Q29tcG9uZW50KCdJbmxpbmUnKTtcbi8qKlxuICogVGhlIGBBdXRvR3JpZGAgY29tcG9uZW50IHJlbmRlcnMgYSByZXNwb25zaXZlIGdyaWQgbGF5b3V0IHRoYXQgYXV0b21hdGljYWxseSBhZGp1c3RzIHRoZSBudW1iZXIgb2YgY29sdW1ucyBiYXNlZCBvbiBhdmFpbGFibGUgc3BhY2UuIFVzZSB0aGlzIGNvbXBvbmVudCB0byBjcmVhdGUgZmxleGlibGUgZ3JpZCBsYXlvdXRzIGZvciBjYXJkcywgdGlsZXMsIG9yIG90aGVyIGNvbnRlbnQuXG4gKlxuICogKipMaW5rczoqKlxuICpcbiAqIC0ge0BsaW5rIGh0dHBzOi8vZGV2ZWxvcGVycy5odWJzcG90LmNvbS9kb2NzL3JlZmVyZW5jZS91aS1jb21wb25lbnRzL3N0YW5kYXJkLWNvbXBvbmVudHMvc2ltcGxlLWdyaWQgRG9jc31cbiAqL1xuZXhwb3J0IGNvbnN0IEF1dG9HcmlkID0gY3JlYXRlQW5kUmVnaXN0ZXJSZW1vdGVSZWFjdENvbXBvbmVudCgnQXV0b0dyaWQnKTtcbi8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vXG4vLyBDUk0gQ09NUE9ORU5UU1xuLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy9cbmV4cG9ydCBjb25zdCBDcm1Qcm9wZXJ0eUxpc3QgPSBjcmVhdGVBbmRSZWdpc3RlclJlbW90ZVJlYWN0Q29tcG9uZW50KCdDcm1Qcm9wZXJ0eUxpc3QnKTtcbmV4cG9ydCBjb25zdCBDcm1Bc3NvY2lhdGlvblRhYmxlID0gY3JlYXRlQW5kUmVnaXN0ZXJSZW1vdGVSZWFjdENvbXBvbmVudCgnQ3JtQXNzb2NpYXRpb25UYWJsZScpO1xuZXhwb3J0IGNvbnN0IENybURhdGFIaWdobGlnaHQgPSBjcmVhdGVBbmRSZWdpc3RlclJlbW90ZVJlYWN0Q29tcG9uZW50KCdDcm1EYXRhSGlnaGxpZ2h0Jyk7XG5leHBvcnQgY29uc3QgQ3JtUmVwb3J0ID0gY3JlYXRlQW5kUmVnaXN0ZXJSZW1vdGVSZWFjdENvbXBvbmVudCgnQ3JtUmVwb3J0Jyk7XG5leHBvcnQgY29uc3QgQ3JtQXNzb2NpYXRpb25QaXZvdCA9IGNyZWF0ZUFuZFJlZ2lzdGVyUmVtb3RlUmVhY3RDb21wb25lbnQoJ0NybUFzc29jaWF0aW9uUGl2b3QnKTtcbmV4cG9ydCBjb25zdCBDcm1Bc3NvY2lhdGlvblByb3BlcnR5TGlzdCA9IGNyZWF0ZUFuZFJlZ2lzdGVyUmVtb3RlUmVhY3RDb21wb25lbnQoJ0NybUFzc29jaWF0aW9uUHJvcGVydHlMaXN0Jyk7XG5leHBvcnQgY29uc3QgQ3JtQXNzb2NpYXRpb25TdGFnZVRyYWNrZXIgPSBjcmVhdGVBbmRSZWdpc3RlclJlbW90ZVJlYWN0Q29tcG9uZW50KCdDcm1Bc3NvY2lhdGlvblN0YWdlVHJhY2tlcicpO1xuZXhwb3J0IGNvbnN0IENybVNpbXBsZURlYWRsaW5lID0gY3JlYXRlQW5kUmVnaXN0ZXJSZW1vdGVSZWFjdENvbXBvbmVudCgnQ3JtU2ltcGxlRGVhZGxpbmUnKTtcbmV4cG9ydCBjb25zdCBDcm1TdGFnZVRyYWNrZXIgPSBjcmVhdGVBbmRSZWdpc3RlclJlbW90ZVJlYWN0Q29tcG9uZW50KCdDcm1TdGFnZVRyYWNrZXInKTtcbmV4cG9ydCBjb25zdCBDcm1TdGF0aXN0aWNzID0gY3JlYXRlQW5kUmVnaXN0ZXJSZW1vdGVSZWFjdENvbXBvbmVudCgnQ3JtU3RhdGlzdGljcycpO1xuZXhwb3J0IGNvbnN0IENybUFjdGlvbkJ1dHRvbiA9IGNyZWF0ZUFuZFJlZ2lzdGVyUmVtb3RlUmVhY3RDb21wb25lbnQoJ0NybUFjdGlvbkJ1dHRvbicpO1xuZXhwb3J0IGNvbnN0IENybUFjdGlvbkxpbmsgPSBjcmVhdGVBbmRSZWdpc3RlclJlbW90ZVJlYWN0Q29tcG9uZW50KCdDcm1BY3Rpb25MaW5rJyk7XG5leHBvcnQgY29uc3QgQ3JtQ2FyZEFjdGlvbnMgPSBjcmVhdGVBbmRSZWdpc3RlclJlbW90ZVJlYWN0Q29tcG9uZW50KCdDcm1DYXJkQWN0aW9ucycpO1xuLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy9cbi8vIEFQUCBIT01FIENPTVBPTkVOVFNcbi8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vXG4vKipcbiAqIFRoZSBgSGVhZGVyQWN0aW9uc2AgY29tcG9uZW50IHJlbmRlcnMgYSBjb250YWluZXIgZm9yIGFjdGlvbiBidXR0b25zIGluIHRoZSBhcHAgaG9tZSBoZWFkZXIuIEl0IGFjY2VwdHMgYFByaW1hcnlIZWFkZXJBY3Rpb25CdXR0b25gIGFuZCBgU2Vjb25kYXJ5SGVhZGVyQWN0aW9uQnV0dG9uYCBhcyBjaGlsZHJlbi5cbiAqXG4gKi9cbmV4cG9ydCBjb25zdCBIZWFkZXJBY3Rpb25zID0gY3JlYXRlQW5kUmVnaXN0ZXJSZW1vdGVSZWFjdENvbXBvbmVudCgnSGVhZGVyQWN0aW9ucycpO1xuLyoqXG4gKiBUaGUgYFByaW1hcnlIZWFkZXJBY3Rpb25CdXR0b25gIGNvbXBvbmVudCByZW5kZXJzIGEgcHJpbWFyeSBhY3Rpb24gYnV0dG9uIGluIHRoZSBhcHAgaG9tZSBoZWFkZXIuIFRoaXMgYnV0dG9uIGlzIHN0eWxlZCBhcyB0aGUgbWFpbiBjYWxsLXRvLWFjdGlvbiBhbmQgb25seSBvbmUgc2hvdWxkIGJlIHVzZWQgcGVyIGBIZWFkZXJBY3Rpb25zYCBjb250YWluZXIuXG4gKlxuICovXG5leHBvcnQgY29uc3QgUHJpbWFyeUhlYWRlckFjdGlvbkJ1dHRvbiA9IGNyZWF0ZUFuZFJlZ2lzdGVyUmVtb3RlUmVhY3RDb21wb25lbnQoJ1ByaW1hcnlIZWFkZXJBY3Rpb25CdXR0b24nLCB7XG4gICAgZnJhZ21lbnRQcm9wczogWydvdmVybGF5J10sXG59KTtcbi8qKlxuICogVGhlIGBTZWNvbmRhcnlIZWFkZXJBY3Rpb25CdXR0b25gIGNvbXBvbmVudCByZW5kZXJzIGEgc2Vjb25kYXJ5IGFjdGlvbiBidXR0b24gaW4gdGhlIGFwcCBob21lIGhlYWRlci4gTXVsdGlwbGUgc2Vjb25kYXJ5IGFjdGlvbnMgY2FuIGJlIHVzZWQgYW5kIHRoZXkgd2lsbCBiZSBncm91cGVkIGFwcHJvcHJpYXRlbHkgaW4gdGhlIGhlYWRlci5cbiAqXG4gKi9cbmV4cG9ydCBjb25zdCBTZWNvbmRhcnlIZWFkZXJBY3Rpb25CdXR0b24gPSBjcmVhdGVBbmRSZWdpc3RlclJlbW90ZVJlYWN0Q29tcG9uZW50KCdTZWNvbmRhcnlIZWFkZXJBY3Rpb25CdXR0b24nLCB7XG4gICAgZnJhZ21lbnRQcm9wczogWydvdmVybGF5J10sXG59KTtcbi8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vXG4vLyBBUFAgUEFHRSBDT01QT05FTlRTXG4vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vL1xuZXhwb3J0IGNvbnN0IFBhZ2VMaW5rID0gY3JlYXRlQW5kUmVnaXN0ZXJSZW1vdGVSZWFjdENvbXBvbmVudCgnUGFnZUxpbmsnKTtcbi8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vXG4vLyBFWFBFUklNRU5UQUwgQ09NUE9ORU5UU1xuLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy8vLy9cbi8qKlxuICogQGV4cGVyaW1lbnRhbCBUaGlzIGNvbXBvbmVudCBpcyBleHBlcmltZW50YWwuIEF2b2lkIHVzaW5nIGl0IGluIHByb2R1Y3Rpb24gZHVlIHRvIHBvdGVudGlhbCBicmVha2luZyBjaGFuZ2VzLiBZb3VyIGZlZWRiYWNrIGlzIHZhbHVhYmxlIGZvciBpbXByb3ZlbWVudHMuIFN0YXkgdHVuZWQgZm9yIHVwZGF0ZXMuXG4gKi9cbmV4cG9ydCBjb25zdCBJZnJhbWUgPSBjcmVhdGVBbmRSZWdpc3RlclJlbW90ZVJlYWN0Q29tcG9uZW50KCdJZnJhbWUnKTtcbi8qKlxuICogQGV4cGVyaW1lbnRhbCBUaGlzIGNvbXBvbmVudCBpcyBleHBlcmltZW50YWwuIEF2b2lkIHVzaW5nIGl0IGluIHByb2R1Y3Rpb24gZHVlIHRvIHBvdGVudGlhbCBicmVha2luZyBjaGFuZ2VzLiBZb3VyIGZlZWRiYWNrIGlzIHZhbHVhYmxlIGZvciBpbXByb3ZlbWVudHMuIFN0YXkgdHVuZWQgZm9yIHVwZGF0ZXMuXG4gKi9cbmV4cG9ydCBjb25zdCBNZWRpYU9iamVjdCA9IGNyZWF0ZUFuZFJlZ2lzdGVyUmVtb3RlUmVhY3RDb21wb25lbnQoJ01lZGlhT2JqZWN0Jywge1xuICAgIGZyYWdtZW50UHJvcHM6IFsnaXRlbVJpZ2h0JywgJ2l0ZW1MZWZ0J10sXG59KTtcbi8qKlxuICogQGV4cGVyaW1lbnRhbCBUaGlzIGNvbXBvbmVudCBpcyBleHBlcmltZW50YWwuIEF2b2lkIHVzaW5nIGl0IGluIHByb2R1Y3Rpb24gZHVlIHRvIHBvdGVudGlhbCBicmVha2luZyBjaGFuZ2VzLiBZb3VyIGZlZWRiYWNrIGlzIHZhbHVhYmxlIGZvciBpbXByb3ZlbWVudHMuIFN0YXkgdHVuZWQgZm9yIHVwZGF0ZXMuXG4gKi9cbmV4cG9ydCBjb25zdCBTdGFjazIgPSBjcmVhdGVBbmRSZWdpc3RlclJlbW90ZVJlYWN0Q29tcG9uZW50KCdTdGFjazInKTtcbi8qKlxuICogQGV4cGVyaW1lbnRhbCBUaGlzIGNvbXBvbmVudCBpcyBleHBlcmltZW50YWwuIEF2b2lkIHVzaW5nIGl0IGluIHByb2R1Y3Rpb24gZHVlIHRvIHBvdGVudGlhbCBicmVha2luZyBjaGFuZ2VzLiBZb3VyIGZlZWRiYWNrIGlzIHZhbHVhYmxlIGZvciBpbXByb3ZlbWVudHMuIFN0YXkgdHVuZWQgZm9yIHVwZGF0ZXMuXG4gKi9cbmV4cG9ydCBjb25zdCBDZW50ZXIgPSBjcmVhdGVBbmRSZWdpc3RlclJlbW90ZVJlYWN0Q29tcG9uZW50KCdDZW50ZXInKTtcbi8qKlxuICogQGV4cGVyaW1lbnRhbCBUaGlzIGNvbXBvbmVudCBpcyBleHBlcmltZW50YWwuIEF2b2lkIHVzaW5nIGl0IGluIHByb2R1Y3Rpb24gZHVlIHRvIHBvdGVudGlhbCBicmVha2luZyBjaGFuZ2VzLiBZb3VyIGZlZWRiYWNrIGlzIHZhbHVhYmxlIGZvciBpbXByb3ZlbWVudHMuIFN0YXkgdHVuZWQgZm9yIHVwZGF0ZXMuXG4gKi9cbmV4cG9ydCBjb25zdCBHcmlkID0gY3JlYXRlQW5kUmVnaXN0ZXJSZW1vdGVSZWFjdENvbXBvbmVudCgnR3JpZCcpO1xuLyoqXG4gKiBAZXhwZXJpbWVudGFsIFRoaXMgY29tcG9uZW50IGlzIGV4cGVyaW1lbnRhbC4gQXZvaWQgdXNpbmcgaXQgaW4gcHJvZHVjdGlvbiBkdWUgdG8gcG90ZW50aWFsIGJyZWFraW5nIGNoYW5nZXMuIFlvdXIgZmVlZGJhY2sgaXMgdmFsdWFibGUgZm9yIGltcHJvdmVtZW50cy4gU3RheSB0dW5lZCBmb3IgdXBkYXRlcy5cbiAqL1xuZXhwb3J0IGNvbnN0IEdyaWRJdGVtID0gY3JlYXRlQW5kUmVnaXN0ZXJSZW1vdGVSZWFjdENvbXBvbmVudCgnR3JpZEl0ZW0nKTtcbi8qKlxuICogQGV4cGVyaW1lbnRhbCBUaGlzIGNvbXBvbmVudCBpcyBleHBlcmltZW50YWwuIEF2b2lkIHVzaW5nIGl0IGluIHByb2R1Y3Rpb24gZHVlIHRvIHBvdGVudGlhbCBicmVha2luZyBjaGFuZ2VzLiBZb3VyIGZlZWRiYWNrIGlzIHZhbHVhYmxlIGZvciBpbXByb3ZlbWVudHMuIFN0YXkgdHVuZWQgZm9yIHVwZGF0ZXMuXG4gKi9cbmV4cG9ydCBjb25zdCBTZXR0aW5nc1ZpZXcgPSBjcmVhdGVBbmRSZWdpc3RlclJlbW90ZVJlYWN0Q29tcG9uZW50KCdTZXR0aW5nc1ZpZXcnKTtcbi8qKlxuICogVGhlIGBFeHBhbmRhYmxlVGV4dGAgY29tcG9uZW50IHJlbmRlcnMgYSB0ZXh0IHRoYXQgY2FuIGJlIGV4cGFuZGVkIG9yIGNvbGxhcHNlZCBiYXNlZCBvbiBhIG1heGltdW0gaGVpZ2h0LlxuICpcbiAqIEBleHBlcmltZW50YWwgVGhpcyBjb21wb25lbnQgaXMgZXhwZXJpbWVudGFsLiBBdm9pZCB1c2luZyBpdCBpbiBwcm9kdWN0aW9uIGR1ZSB0byBwb3RlbnRpYWwgYnJlYWtpbmcgY2hhbmdlcy4gWW91ciBmZWVkYmFjayBpcyB2YWx1YWJsZSBmb3IgaW1wcm92ZW1lbnRzLiBTdGF5IHR1bmVkIGZvciB1cGRhdGVzLlxuICpcbiAqICoqTGlua3M6KipcbiAqXG4gKiAtIHtAbGluayBodHRwczovL2RldmVsb3BlcnMuaHVic3BvdC5jb20vZG9jcy9yZWZlcmVuY2UvdWktY29tcG9uZW50cy9zdGFuZGFyZC1jb21wb25lbnRzL2V4cGFuZGFibGUtdGV4dCBFeHBhbmRhYmxlVGV4dCBEb2NzfVxuICovXG5leHBvcnQgY29uc3QgRXhwYW5kYWJsZVRleHQgPSBjcmVhdGVBbmRSZWdpc3RlclJlbW90ZVJlYWN0Q29tcG9uZW50KCdFeHBhbmRhYmxlVGV4dCcpO1xuLyoqXG4gKiBUaGUgYFBvcG92ZXJgIGNvbXBvbmVudCByZW5kZXJzIGEgcG9wb3ZlciBvdmVybGF5IHRoYXQgY2FuIGNvbnRhaW4gb3RoZXIgY29tcG9uZW50cy5cbiAqXG4gKiBAZXhwZXJpbWVudGFsIFRoaXMgY29tcG9uZW50IGlzIGV4cGVyaW1lbnRhbC4gQXZvaWQgdXNpbmcgaXQgaW4gcHJvZHVjdGlvbiBkdWUgdG8gcG90ZW50aWFsIGJyZWFraW5nIGNoYW5nZXMuIFlvdXIgZmVlZGJhY2sgaXMgdmFsdWFibGUgZm9yIGltcHJvdmVtZW50cy4gU3RheSB0dW5lZCBmb3IgdXBkYXRlcy5cbiAqXG4gKiAqKkxpbmtzOioqXG4gKlxuICogLSB7QGxpbmsgaHR0cHM6Ly9kZXZlbG9wZXJzLmh1YnNwb3QuY29tL2RvY3MvcmVmZXJlbmNlL3VpLWNvbXBvbmVudHMvc3RhbmRhcmQtY29tcG9uZW50cy9wb3BvdmVyIFBvcG92ZXIgRG9jc31cbiAqL1xuZXhwb3J0IGNvbnN0IFBvcG92ZXIgPSBjcmVhdGVBbmRSZWdpc3RlclJlbW90ZVJlYWN0Q29tcG9uZW50KCdQb3BvdmVyJyk7XG4vKipcbiAqIEBleHBlcmltZW50YWwgVGhpcyBjb21wb25lbnQgaXMgZXhwZXJpbWVudGFsLiBBdm9pZCB1c2luZyBpdCBpbiBwcm9kdWN0aW9uIGR1ZSB0byBwb3RlbnRpYWwgYnJlYWtpbmcgY2hhbmdlcy4gWW91ciBmZWVkYmFjayBpcyB2YWx1YWJsZSBmb3IgaW1wcm92ZW1lbnRzLiBTdGF5IHR1bmVkIGZvciB1cGRhdGVzLlxuICovXG5leHBvcnQgY29uc3QgRmlsZUlucHV0ID0gY3JlYXRlQW5kUmVnaXN0ZXJSZW1vdGVSZWFjdENvbXBvbmVudCgnRmlsZUlucHV0Jyk7XG4iLCJpbXBvcnQgeyBjcmVhdGVDb250ZXh0LCB1c2VDb250ZXh0IH0gZnJvbSAncmVhY3QnO1xuY29uc3QgTW9ja3NDb250ZXh0ID0gY3JlYXRlQ29udGV4dChudWxsKTtcbi8qKlxuICogQ3JlYXRlcyBhIG1vY2stYXdhcmUgaG9vayBmdW5jdGlvbiB0aGF0IGNhbiBiZSB1c2VkIHRvIG1vY2sgdGhlIG9yaWdpbmFsIGhvb2sgZnVuY3Rpb24uXG4gKiBUaGUgbW9jay1hd2FyZSBob29rIGZ1bmN0aW9uIHdpbGwgcmV0dXJuIHRoZSBtb2NrZWQgaG9vayBmdW5jdGlvbiBpZiBhIG1vY2sgaXMgZm91bmQsIG90aGVyd2lzZSBpdCB3aWxsIHJldHVybiB0aGUgb3JpZ2luYWwgaG9vayBmdW5jdGlvbi5cbiAqXG4gKiBAcGFyYW0gaG9va05hbWUgVGhlIG5hbWUgb2YgdGhlIGhvb2sgdG8gbW9jayB0aGF0IGNvcnJlc3BvbmRzIHRvIHRoZSBrZXkgaW4gdGhlIE1vY2tzIGludGVyZmFjZVxuICogQHBhcmFtIG9yaWdpbmFsSG9va0Z1bmN0aW9uIFRoZSBvcmlnaW5hbCBob29rIGZ1bmN0aW9uIHRvIGNhbGwgaWYgbm8gbW9jayBpcyBmb3VuZFxuICogQHJldHVybnMgVGhlIG1vY2tlZCBob29rIGZ1bmN0aW9uIG9yIHRoZSBvcmlnaW5hbCBob29rIGZ1bmN0aW9uIGlmIG5vIG1vY2sgaXMgZm91bmRcbiAqL1xuZXhwb3J0IGNvbnN0IGNyZWF0ZU1vY2tBd2FyZUhvb2sgPSAoaG9va05hbWUsIG9yaWdpbmFsSG9va0Z1bmN0aW9uKSA9PiB7XG4gICAgY29uc3QgdXNlV3JhcHBlciA9ICguLi5hcmdzKSA9PiB7XG4gICAgICAgIGNvbnN0IG1vY2tzID0gdXNlTW9ja3NDb250ZXh0KCk7XG4gICAgICAgIGlmICghbW9ja3MpIHtcbiAgICAgICAgICAgIC8vIElmIG5vIG1vY2tzIGFyZSBwcm92aWRlZCwgY2FsbCB0aGUgb3JpZ2luYWwgaG9vayBmdW5jdGlvblxuICAgICAgICAgICAgcmV0dXJuIG9yaWdpbmFsSG9va0Z1bmN0aW9uKC4uLmFyZ3MpO1xuICAgICAgICB9XG4gICAgICAgIC8vIFdoZW4gYSBtb2NrIGlzIHByb3ZpZGVkIGJ5IHRoZSB0ZXN0aW5nIHV0aWxpdGllcyAodmlhIDxNb2Nrc0NvbnRleHRQcm92aWRlcj4pLCByZXR1cm4gdGhlIG1vY2tlZCBob29rIGZ1bmN0aW9uXG4gICAgICAgIGNvbnN0IG1vY2tIb29rID0gbW9ja3NbaG9va05hbWVdO1xuICAgICAgICBpZiAoIW1vY2tIb29rKSB7XG4gICAgICAgICAgICB0aHJvdyBuZXcgRXJyb3IoYElsbGVnYWwgU3RhdGU6IE1vY2sgZm9yIGhvb2sgJHtob29rTmFtZX0gbm90IGZvdW5kLmApO1xuICAgICAgICB9XG4gICAgICAgIC8vIENhbGwgdGhlIG1vY2tlZCBob29rIGZ1bmN0aW9uIHdpdGggdGhlIHNhbWUgYXJndW1lbnRzIGFzIHRoZSBvcmlnaW5hbCBob29rIGZ1bmN0aW9uIGFuZCByZXR1cm4gdGhlIHJlc3VsdFxuICAgICAgICByZXR1cm4gbW9ja0hvb2soLi4uYXJncyk7XG4gICAgfTtcbiAgICByZXR1cm4gdXNlV3JhcHBlcjtcbn07XG4vKipcbiAqIEEgaG9vayB0aGF0IHByb3ZpZGVzIGFjY2VzcyB0byB0aGUgTW9ja3MgY29udGV4dC5cbiAqIFJldHVybnMgdGhlIG1vY2tzIG9iamVjdCBpZiBpbnNpZGUgYSBNb2Nrc0NvbnRleHRQcm92aWRlciwgb3RoZXJ3aXNlIHJldHVybnMgbnVsbC5cbiAqXG4gKiBAcmV0dXJucyBUaGUgbW9ja3Mgb2JqZWN0IG9yIG51bGwgaWYgbm90IGluIGEgdGVzdCBlbnZpcm9ubWVudC5cbiAqL1xuZXhwb3J0IGZ1bmN0aW9uIHVzZU1vY2tzQ29udGV4dCgpIHtcbiAgICByZXR1cm4gdXNlQ29udGV4dChNb2Nrc0NvbnRleHQpO1xufVxuLyoqXG4gKiBBIFJlYWN0IGNvbXBvbmVudCB0aGF0IHByb3ZpZGVzIHRoZSBNb2NrcyBjb250ZXh0IHRoYXQgY2FuIGJlIHVzZWQgdG8gcHJvdmlkZSBtb2NrcyB0byB0aGUgbW9jay1hd2FyZSBob29rIGZ1bmN0aW9ucy5cbiAqXG4gKiBAcGFyYW0gY2hpbGRyZW4gVGhlIGNoaWxkcmVuIHRvIHJlbmRlci5cbiAqIEByZXR1cm5zIFRoZSBjaGlsZHJlbiB3cmFwcGVkIGluIHRoZSBNb2NrcyBjb250ZXh0IHByb3ZpZGVyLlxuICovXG5leHBvcnQgY29uc3QgTW9ja3NDb250ZXh0UHJvdmlkZXIgPSBNb2Nrc0NvbnRleHQuUHJvdmlkZXI7XG4iLCJcclxuaW1wb3J0IFJlYWN0LCB7IHVzZUVmZmVjdCwgdXNlU3RhdGUgfSBmcm9tIFwicmVhY3RcIjtcclxuaW1wb3J0IHtcclxuICBCb3gsXHJcbiAgQnV0dG9uLFxyXG4gIERpdmlkZXIsXHJcbiAgRW1wdHlTdGF0ZSxcclxuICBGbGV4LFxyXG4gIEZvcm0sXHJcbiAgSW5wdXQsXHJcbiAgU2VsZWN0LFxyXG4gIFRleHQsXHJcbiAgVGV4dEFyZWEsXHJcbiAgaHVic3BvdCxcclxufSBmcm9tIFwiQGh1YnNwb3QvdWktZXh0ZW5zaW9uc1wiO1xyXG5cclxuY29uc3QgQkFDS0VORF9CQVNFX1VSTCA9IFwiaHR0cHM6Ly9vcHNsZW5zLmxvY2FsXCI7XHJcblxyXG5odWJzcG90LmV4dGVuZCgoeyBjb250ZXh0IH0pID0+IHtcclxuICByZXR1cm4gPFNldHRpbmdzUGFnZSBjb250ZXh0PXtjb250ZXh0fSAvPjtcclxufSk7XHJcblxyXG5jb25zdCBTZXR0aW5nc1BhZ2UgPSAoeyBjb250ZXh0IH0pID0+IHtcclxuICBjb25zdCBbbG9hZGluZywgc2V0TG9hZGluZ10gPSB1c2VTdGF0ZSh0cnVlKTtcclxuICBjb25zdCBbc2F2ZU1lc3NhZ2UsIHNldFNhdmVNZXNzYWdlXSA9IHVzZVN0YXRlKFwiXCIpO1xyXG4gIGNvbnN0IFtlcnJvck1lc3NhZ2UsIHNldEVycm9yTWVzc2FnZV0gPSB1c2VTdGF0ZShcIlwiKTtcclxuICBjb25zdCBbc2xhY2tXZWJob29rVXJsLCBzZXRTbGFja1dlYmhvb2tVcmxdID0gdXNlU3RhdGUoXCJcIik7XHJcbiAgY29uc3QgW2FsZXJ0VGhyZXNob2xkLCBzZXRBbGVydFRocmVzaG9sZF0gPSB1c2VTdGF0ZShcImhpZ2hcIik7XHJcbiAgY29uc3QgW2NyaXRpY2FsV29ya2Zsb3dzLCBzZXRDcml0aWNhbFdvcmtmbG93c10gPSB1c2VTdGF0ZShcIlwiKTtcclxuXHJcbiAgY29uc3QgbG9hZFNldHRpbmdzID0gYXN5bmMgKCkgPT4ge1xyXG4gICAgc2V0TG9hZGluZyh0cnVlKTtcclxuICAgIHNldEVycm9yTWVzc2FnZShcIlwiKTtcclxuICAgIHNldFNhdmVNZXNzYWdlKFwiXCIpO1xyXG5cclxuICAgIHRyeSB7XHJcbiAgICAgIGNvbnN0IHJlc3BvbnNlID0gYXdhaXQgaHVic3BvdC5mZXRjaChcclxuICBgJHtCQUNLRU5EX0JBU0VfVVJMfS9hcGkvdjEvc2V0dGluZ3Mtc3RvcmVgLFxyXG4gIHtcclxuICAgIG1ldGhvZDogXCJHRVRcIixcclxuICAgIHRpbWVvdXQ6IDMwMDAsXHJcbiAgfVxyXG4pO1xyXG5cclxuICAgICAgaWYgKCFyZXNwb25zZS5vaykge1xyXG4gICAgICAgIHRocm93IG5ldyBFcnJvcihgQmFja2VuZCByZXR1cm5lZCBzdGF0dXMgJHtyZXNwb25zZS5zdGF0dXN9YCk7XHJcbiAgICAgIH1cclxuXHJcbiAgICAgIGNvbnN0IGRhdGEgPSBhd2FpdCByZXNwb25zZS5qc29uKCk7XHJcbiAgICAgIHNldFNsYWNrV2ViaG9va1VybChkYXRhPy5zZXR0aW5ncz8uc2xhY2tXZWJob29rVXJsID8/IFwiXCIpO1xyXG4gICAgICBzZXRBbGVydFRocmVzaG9sZChkYXRhPy5zZXR0aW5ncz8uYWxlcnRUaHJlc2hvbGQgPz8gXCJoaWdoXCIpO1xyXG4gICAgICBzZXRDcml0aWNhbFdvcmtmbG93cyhkYXRhPy5zZXR0aW5ncz8uY3JpdGljYWxXb3JrZmxvd3MgPz8gXCJcIik7XHJcbiAgICB9IGNhdGNoIChlcnIpIHtcclxuICAgICAgY29uc29sZS5lcnJvcihcIkZhaWxlZCB0byBsb2FkIHNldHRpbmdzXCIsIGVycik7XHJcbiAgICAgIHNldEVycm9yTWVzc2FnZShlcnIgaW5zdGFuY2VvZiBFcnJvciA/IGVyci5tZXNzYWdlIDogXCJVbmtub3duIGVycm9yXCIpO1xyXG4gICAgfSBmaW5hbGx5IHtcclxuICAgICAgc2V0TG9hZGluZyhmYWxzZSk7XHJcbiAgICB9XHJcbiAgfTtcclxuXHJcbiAgY29uc3Qgc2F2ZVNldHRpbmdzID0gYXN5bmMgKCkgPT4ge1xyXG4gICAgc2V0RXJyb3JNZXNzYWdlKFwiXCIpO1xyXG4gICAgc2V0U2F2ZU1lc3NhZ2UoXCJcIik7XHJcblxyXG4gICAgdHJ5IHtcclxuICAgICAgY29uc3QgcmVzcG9uc2UgPSBhd2FpdCBodWJzcG90LmZldGNoKFxyXG4gIGAke0JBQ0tFTkRfQkFTRV9VUkx9L2FwaS92MS9zZXR0aW5ncy1zdG9yZWAsXHJcbiAge1xyXG4gICAgbWV0aG9kOiBcIlBPU1RcIixcclxuICAgIHRpbWVvdXQ6IDMwMDAsXHJcbiAgICBib2R5OiB7XHJcbiAgICAgIHNsYWNrV2ViaG9va1VybCxcclxuICAgICAgYWxlcnRUaHJlc2hvbGQsXHJcbiAgICAgIGNyaXRpY2FsV29ya2Zsb3dzLFxyXG4gICAgfSxcclxuICB9XHJcbik7XHJcblxyXG4gICAgICBpZiAoIXJlc3BvbnNlLm9rKSB7XHJcbiAgICAgICAgdGhyb3cgbmV3IEVycm9yKGBCYWNrZW5kIHJldHVybmVkIHN0YXR1cyAke3Jlc3BvbnNlLnN0YXR1c31gKTtcclxuICAgICAgfVxyXG5cclxuICAgICAgY29uc3QgZGF0YSA9IGF3YWl0IHJlc3BvbnNlLmpzb24oKTtcclxuICAgICAgc2V0U2F2ZU1lc3NhZ2UoYFNhdmVkIGF0ICR7ZGF0YS5zYXZlZEF0VXRjfWApO1xyXG4gICAgfSBjYXRjaCAoZXJyKSB7XHJcbiAgICAgIGNvbnNvbGUuZXJyb3IoXCJGYWlsZWQgdG8gc2F2ZSBzZXR0aW5nc1wiLCBlcnIpO1xyXG4gICAgICBzZXRFcnJvck1lc3NhZ2UoZXJyIGluc3RhbmNlb2YgRXJyb3IgPyBlcnIubWVzc2FnZSA6IFwiVW5rbm93biBlcnJvclwiKTtcclxuICAgIH1cclxuICB9O1xyXG5cclxuICB1c2VFZmZlY3QoKCkgPT4ge1xyXG4gICAgbG9hZFNldHRpbmdzKCkuY2F0Y2goKGVycikgPT5cclxuICAgICAgY29uc29sZS5lcnJvcihcIlVuZXhwZWN0ZWQgc2V0dGluZ3MgbG9hZCBlcnJvclwiLCBlcnIpXHJcbiAgICApO1xyXG4gIH0sIFtdKTtcclxuXHJcbiAgcmV0dXJuIChcclxuICAgIDxGbGV4IGRpcmVjdGlvbj1cImNvbHVtblwiIGdhcD1cIm1lZGl1bVwiPlxyXG4gICAgICA8RW1wdHlTdGF0ZSB0aXRsZT1cIk9wc0xlbnMgQUkgc2V0dGluZ3NcIiBsYXlvdXQ9XCJ2ZXJ0aWNhbFwiPlxyXG4gICAgICAgIDxUZXh0PlxyXG4gICAgICAgICAgVGhpcyBwYWdlIG5vdyBsb2FkcyBhbmQgc2F2ZXMgcG9ydGFsLWxldmVsIE9wc0xlbnMgc2V0dGluZ3MgdGhyb3VnaCB0aGUgbG9jYWwgUHl0aG9uIGJhY2tlbmQuXHJcbiAgICAgICAgPC9UZXh0PlxyXG4gICAgICA8L0VtcHR5U3RhdGU+XHJcblxyXG4gICAgICA8RGl2aWRlciAvPlxyXG5cclxuICAgICAgPEJveD5cclxuICAgICAgICA8VGV4dCBmb3JtYXQ9e3sgZm9udFdlaWdodDogXCJib2xkXCIgfX0+QmFja2VuZCBzdGF0dXM8L1RleHQ+XHJcbiAgICAgICAgPFRleHQ+e2xvYWRpbmcgPyBcIkxvYWRpbmcgc2V0dGluZ3MuLi5cIiA6IFwiUmVhZHlcIn08L1RleHQ+XHJcbiAgICAgICAgPFRleHQ+e2Vycm9yTWVzc2FnZSA/IGBFcnJvcjogJHtlcnJvck1lc3NhZ2V9YCA6IFwiTm8gc2V0dGluZ3MgZmV0Y2ggZXJyb3IgZGV0ZWN0ZWQuXCJ9PC9UZXh0PlxyXG4gICAgICAgIDxUZXh0PntzYXZlTWVzc2FnZSA/IHNhdmVNZXNzYWdlIDogXCJObyBzZXR0aW5ncyBzYXZlIGV2ZW50IHlldC5cIn08L1RleHQ+XHJcbiAgICAgIDwvQm94PlxyXG5cclxuICAgICAgPERpdmlkZXIgLz5cclxuXHJcbiAgICAgIDxGb3JtXHJcbiAgICAgICAgcHJldmVudERlZmF1bHQ9e3RydWV9XHJcbiAgICAgICAgb25TdWJtaXQ9eygpID0+IHtcclxuICAgICAgICAgIHNhdmVTZXR0aW5ncygpLmNhdGNoKChlcnIpID0+XHJcbiAgICAgICAgICAgIGNvbnNvbGUuZXJyb3IoXCJVbmV4cGVjdGVkIHNldHRpbmdzIHNhdmUgZXJyb3JcIiwgZXJyKVxyXG4gICAgICAgICAgKTtcclxuICAgICAgICB9fVxyXG4gICAgICA+XHJcbiAgICAgICAgPEZsZXggZGlyZWN0aW9uPVwiY29sdW1uXCIgZ2FwPVwibWVkaXVtXCI+XHJcbiAgICAgICAgICA8SW5wdXRcclxuICAgICAgICAgICAgbGFiZWw9XCJTbGFjayB3ZWJob29rIFVSTFwiXHJcbiAgICAgICAgICAgIG5hbWU9XCJzbGFja1dlYmhvb2tVcmxcIlxyXG4gICAgICAgICAgICB2YWx1ZT17c2xhY2tXZWJob29rVXJsfVxyXG4gICAgICAgICAgICBvbkNoYW5nZT17KHZhbHVlKSA9PiBzZXRTbGFja1dlYmhvb2tVcmwodmFsdWUpfVxyXG4gICAgICAgICAgICBwbGFjZWhvbGRlcj1cImh0dHBzOi8vaG9va3Muc2xhY2suY29tL3NlcnZpY2VzLy4uLlwiXHJcbiAgICAgICAgICAvPlxyXG5cclxuICAgICAgICAgIDxTZWxlY3RcclxuICAgICAgICAgICAgbGFiZWw9XCJBbGVydCB0aHJlc2hvbGRcIlxyXG4gICAgICAgICAgICBuYW1lPVwiYWxlcnRUaHJlc2hvbGRcIlxyXG4gICAgICAgICAgICB2YWx1ZT17YWxlcnRUaHJlc2hvbGR9XHJcbiAgICAgICAgICAgIG9uQ2hhbmdlPXsodmFsdWUpID0+IHNldEFsZXJ0VGhyZXNob2xkKFN0cmluZyh2YWx1ZSkpfVxyXG4gICAgICAgICAgICBvcHRpb25zPXtbXHJcbiAgICAgICAgICAgICAgeyBsYWJlbDogXCJDcml0aWNhbFwiLCB2YWx1ZTogXCJjcml0aWNhbFwiIH0sXHJcbiAgICAgICAgICAgICAgeyBsYWJlbDogXCJIaWdoXCIsIHZhbHVlOiBcImhpZ2hcIiB9LFxyXG4gICAgICAgICAgICAgIHsgbGFiZWw6IFwiTWVkaXVtXCIsIHZhbHVlOiBcIm1lZGl1bVwiIH0sXHJcbiAgICAgICAgICAgIF19XHJcbiAgICAgICAgICAvPlxyXG5cclxuICAgICAgICAgIDxUZXh0QXJlYVxyXG4gICAgICAgICAgICBsYWJlbD1cIkNyaXRpY2FsIHdvcmtmbG93c1wiXHJcbiAgICAgICAgICAgIG5hbWU9XCJjcml0aWNhbFdvcmtmbG93c1wiXHJcbiAgICAgICAgICAgIHZhbHVlPXtjcml0aWNhbFdvcmtmbG93c31cclxuICAgICAgICAgICAgb25DaGFuZ2U9eyh2YWx1ZSkgPT4gc2V0Q3JpdGljYWxXb3JrZmxvd3ModmFsdWUpfVxyXG4gICAgICAgICAgICBwbGFjZWhvbGRlcj17XCJRdW90ZSBTeW5jXFxuT3duZXIgUm91dGluZ1xcbkltcG9ydCBDbGVhbnVwXCJ9XHJcbiAgICAgICAgICAgIGRlc2NyaXB0aW9uPVwiT25lIHdvcmtmbG93IG5hbWUgcGVyIGxpbmUuXCJcclxuICAgICAgICAgIC8+XHJcblxyXG4gICAgICAgICAgPEJ1dHRvbiB0eXBlPVwic3VibWl0XCI+U2F2ZSBzZXR0aW5nczwvQnV0dG9uPlxyXG4gICAgICAgIDwvRmxleD5cclxuICAgICAgPC9Gb3JtPlxyXG5cclxuICAgICAgPERpdmlkZXIgLz5cclxuXHJcbiAgICAgIDxCb3g+XHJcbiAgICAgICAgPFRleHQgZm9ybWF0PXt7IGZvbnRXZWlnaHQ6IFwiYm9sZFwiIH19PkRlYnVnIGNvbnRleHQ8L1RleHQ+XHJcbiAgICAgICAgPFRleHQ+UG9ydGFsIElEOiB7U3RyaW5nKGNvbnRleHQ/LnBvcnRhbD8uaWQgPz8gXCJ1bmtub3duXCIpfTwvVGV4dD5cclxuICAgICAgICA8VGV4dD5Vc2VyIElEOiB7U3RyaW5nKGNvbnRleHQ/LnVzZXI/LmlkID8/IFwidW5rbm93blwiKX08L1RleHQ+XHJcbiAgICAgIDwvQm94PlxyXG4gICAgPC9GbGV4PlxyXG4gICk7XHJcbn07XHJcbiJdLCJuYW1lcyI6WyJTZXJ2ZXJsZXNzRXhlY3V0aW9uU3RhdHVzIiwiUmVhY3QiLCJyZXF1aXJlJCQwIiwiUmVhY3REZWJ1Z0N1cnJlbnRGcmFtZSIsInNlbGYiLCJqc3hSdW50aW1lTW9kdWxlIiwiY3JlYXRlUmVtb3RlUmVhY3RDb21wb25lbnQiLCJfanN4IiwiY3JlYXRlQ29udGV4dCIsInVzZVN0YXRlIiwiX2EiLCJfYiIsInVzZUVmZmVjdCJdLCJtYXBwaW5ncyI6Ijs7QUFJQSxRQUFNLG9CQUFvQixNQUFNLE9BQU8sU0FBUyxlQUM1QyxLQUFLLGlDQUFpQztBQUkxQyxRQUFNLG9CQUFvQjtBQUFBLElBQ3RCLFFBQVE7QUFBQSxNQUNKLE9BQU8sQ0FBQyxTQUFTO0FBQ2IsZ0JBQVEsSUFBSSxJQUFJO0FBQUEsTUFDcEI7QUFBQSxNQUNBLE1BQU0sQ0FBQyxTQUFTO0FBQ1osZ0JBQVEsS0FBSyxJQUFJO0FBQUEsTUFDckI7QUFBQSxNQUNBLE1BQU0sQ0FBQyxTQUFTO0FBQ1osZ0JBQVEsS0FBSyxJQUFJO0FBQUEsTUFDckI7QUFBQSxNQUNBLE9BQU8sQ0FBQyxTQUFTO0FBQ2IsZ0JBQVEsTUFBTSxJQUFJO0FBQUEsTUFDdEI7QUFBQSxJQUNSO0FBQUEsSUFDSSxXQUFXLE1BQU07QUFBQSxJQUVqQjtBQUFBO0FBQUEsSUFFQSx1QkFBdUIsTUFBTTtBQUFBLElBRTdCO0FBQUEsRUFDSjtBQUtPLFFBQU0sbUJBQW1CLE1BQU07QUFDbEMsV0FBTyxrQkFBaUIsSUFDbEIsT0FDQTtBQUFBLEVBQ1Y7QUN2Q0EsUUFBTSxZQUFZLGlCQUFnQixFQUFHO0FBQzlCLFdBQVMsV0FBVyxNQUFNLFNBQVM7QUFDdEMsV0FBTyxLQUFLLFdBQVcsTUFBTSxPQUFPO0FBQUEsRUFDeEM7QUFDTyxXQUFTLE1BQU0sS0FBSyxTQUFTO0FBQ2hDLFdBQU8sS0FBSyxRQUFRLEtBQUssT0FBTztBQUFBLEVBQ3BDO0FBQ08sUUFBTSxVQUFVO0FBQUEsSUFDbkIsUUFBUTtBQUFBLElBQ1I7QUFBQSxJQUNBO0FBQUEsRUFDSjtBQ1RPLE1BQUk7QUFDWCxHQUFDLFNBQVVBLDRCQUEyQjtBQUNsQyxJQUFBQSwyQkFBMEIsU0FBUyxJQUFJO0FBQ3ZDLElBQUFBLDJCQUEwQixPQUFPLElBQUk7QUFBQSxFQUN6QyxHQUFHLDhCQUE4Qiw0QkFBNEIsQ0FBQSxFQUFHOzs7Ozs7O0lDUGhFO0FBQUE7QUFBQTtBQUFBO0FBQUE7QUFBQTtBQUFBO0FBQUE7QUFBQTtBQVkyQztBQUN6QyxPQUFDLFdBQVc7QUFHZCxZQUFJQyxVQUFRQztBQU1aLFlBQUkscUJBQXFCLE9BQU8sSUFBSSxlQUFlO0FBQ25ELFlBQUksb0JBQW9CLE9BQU8sSUFBSSxjQUFjO0FBQ2pELFlBQUksc0JBQXNCLE9BQU8sSUFBSSxnQkFBZ0I7QUFDckQsWUFBSSx5QkFBeUIsT0FBTyxJQUFJLG1CQUFtQjtBQUMzRCxZQUFJLHNCQUFzQixPQUFPLElBQUksZ0JBQWdCO0FBQ3JELFlBQUksc0JBQXNCLE9BQU8sSUFBSSxnQkFBZ0I7QUFDckQsWUFBSSxxQkFBcUIsT0FBTyxJQUFJLGVBQWU7QUFDbkQsWUFBSSx5QkFBeUIsT0FBTyxJQUFJLG1CQUFtQjtBQUMzRCxZQUFJLHNCQUFzQixPQUFPLElBQUksZ0JBQWdCO0FBQ3JELFlBQUksMkJBQTJCLE9BQU8sSUFBSSxxQkFBcUI7QUFDL0QsWUFBSSxrQkFBa0IsT0FBTyxJQUFJLFlBQVk7QUFDN0MsWUFBSSxrQkFBa0IsT0FBTyxJQUFJLFlBQVk7QUFDN0MsWUFBSSx1QkFBdUIsT0FBTyxJQUFJLGlCQUFpQjtBQUN2RCxZQUFJLHdCQUF3QixPQUFPO0FBQ25DLFlBQUksdUJBQXVCO0FBQzNCLGlCQUFTLGNBQWMsZUFBZTtBQUNwQyxjQUFJLGtCQUFrQixRQUFRLE9BQU8sa0JBQWtCLFVBQVU7QUFDL0QsbUJBQU87QUFBQSxVQUFBO0FBR1QsY0FBSSxnQkFBZ0IseUJBQXlCLGNBQWMscUJBQXFCLEtBQUssY0FBYyxvQkFBb0I7QUFFdkgsY0FBSSxPQUFPLGtCQUFrQixZQUFZO0FBQ3ZDLG1CQUFPO0FBQUEsVUFBQTtBQUdULGlCQUFPO0FBQUEsUUFBQTtBQUdULFlBQUksdUJBQXVCRCxRQUFNO0FBRWpDLGlCQUFTLE1BQU0sUUFBUTtBQUNyQjtBQUNFO0FBQ0UsdUJBQVMsUUFBUSxVQUFVLFFBQVEsT0FBTyxJQUFJLE1BQU0sUUFBUSxJQUFJLFFBQVEsSUFBSSxDQUFDLEdBQUcsUUFBUSxHQUFHLFFBQVEsT0FBTyxTQUFTO0FBQ2pILHFCQUFLLFFBQVEsQ0FBQyxJQUFJLFVBQVUsS0FBSztBQUFBLGNBQUE7QUFHbkMsMkJBQWEsU0FBUyxRQUFRLElBQUk7QUFBQSxZQUFBO0FBQUEsVUFDcEM7QUFBQSxRQUNGO0FBR0YsaUJBQVMsYUFBYSxPQUFPLFFBQVEsTUFBTTtBQUd6QztBQUNFLGdCQUFJRSwwQkFBeUIscUJBQXFCO0FBQ2xELGdCQUFJLFFBQVFBLHdCQUF1QixpQkFBQTtBQUVuQyxnQkFBSSxVQUFVLElBQUk7QUFDaEIsd0JBQVU7QUFDVixxQkFBTyxLQUFLLE9BQU8sQ0FBQyxLQUFLLENBQUM7QUFBQSxZQUFBO0FBSTVCLGdCQUFJLGlCQUFpQixLQUFLLElBQUksU0FBVSxNQUFNO0FBQzVDLHFCQUFPLE9BQU8sSUFBSTtBQUFBLFlBQUEsQ0FDbkI7QUFFRCwyQkFBZSxRQUFRLGNBQWMsTUFBTTtBQUkzQyxxQkFBUyxVQUFVLE1BQU0sS0FBSyxRQUFRLEtBQUssR0FBRyxTQUFTLGNBQWM7QUFBQSxVQUFBO0FBQUEsUUFDdkU7QUFLRixZQUFJLGlCQUFpQjtBQUNyQixZQUFJLHFCQUFxQjtBQUN6QixZQUFJLDBCQUEwQjtBQUU5QixZQUFJLHFCQUFxQjtBQUl6QixZQUFJLHFCQUFxQjtBQUV6QixZQUFJO0FBRUo7QUFDRSxtQ0FBeUIsT0FBTyxJQUFJLHdCQUF3QjtBQUFBLFFBQUE7QUFHOUQsaUJBQVMsbUJBQW1CLE1BQU07QUFDaEMsY0FBSSxPQUFPLFNBQVMsWUFBWSxPQUFPLFNBQVMsWUFBWTtBQUMxRCxtQkFBTztBQUFBLFVBQUE7QUFJVCxjQUFJLFNBQVMsdUJBQXVCLFNBQVMsdUJBQXVCLHNCQUF1QixTQUFTLDBCQUEwQixTQUFTLHVCQUF1QixTQUFTLDRCQUE0QixzQkFBdUIsU0FBUyx3QkFBd0Isa0JBQW1CLHNCQUF1Qix5QkFBMEI7QUFDN1QsbUJBQU87QUFBQSxVQUFBO0FBR1QsY0FBSSxPQUFPLFNBQVMsWUFBWSxTQUFTLE1BQU07QUFDN0MsZ0JBQUksS0FBSyxhQUFhLG1CQUFtQixLQUFLLGFBQWEsbUJBQW1CLEtBQUssYUFBYSx1QkFBdUIsS0FBSyxhQUFhLHNCQUFzQixLQUFLLGFBQWE7QUFBQTtBQUFBO0FBQUE7QUFBQSxZQUlqTCxLQUFLLGFBQWEsMEJBQTBCLEtBQUssZ0JBQWdCLFFBQVc7QUFDMUUscUJBQU87QUFBQSxZQUFBO0FBQUEsVUFDVDtBQUdGLGlCQUFPO0FBQUEsUUFBQTtBQUdULGlCQUFTLGVBQWUsV0FBVyxXQUFXLGFBQWE7QUFDekQsY0FBSSxjQUFjLFVBQVU7QUFFNUIsY0FBSSxhQUFhO0FBQ2YsbUJBQU87QUFBQSxVQUFBO0FBR1QsY0FBSSxlQUFlLFVBQVUsZUFBZSxVQUFVLFFBQVE7QUFDOUQsaUJBQU8saUJBQWlCLEtBQUssY0FBYyxNQUFNLGVBQWUsTUFBTTtBQUFBLFFBQUE7QUFJeEUsaUJBQVMsZUFBZSxNQUFNO0FBQzVCLGlCQUFPLEtBQUssZUFBZTtBQUFBLFFBQUE7QUFJN0IsaUJBQVMseUJBQXlCLE1BQU07QUFDdEMsY0FBSSxRQUFRLE1BQU07QUFFaEIsbUJBQU87QUFBQSxVQUFBO0FBR1Q7QUFDRSxnQkFBSSxPQUFPLEtBQUssUUFBUSxVQUFVO0FBQ2hDLG9CQUFNLG1IQUF3SDtBQUFBLFlBQUE7QUFBQSxVQUNoSTtBQUdGLGNBQUksT0FBTyxTQUFTLFlBQVk7QUFDOUIsbUJBQU8sS0FBSyxlQUFlLEtBQUssUUFBUTtBQUFBLFVBQUE7QUFHMUMsY0FBSSxPQUFPLFNBQVMsVUFBVTtBQUM1QixtQkFBTztBQUFBLFVBQUE7QUFHVCxrQkFBUSxNQUFBO0FBQUEsWUFDTixLQUFLO0FBQ0gscUJBQU87QUFBQSxZQUVULEtBQUs7QUFDSCxxQkFBTztBQUFBLFlBRVQsS0FBSztBQUNILHFCQUFPO0FBQUEsWUFFVCxLQUFLO0FBQ0gscUJBQU87QUFBQSxZQUVULEtBQUs7QUFDSCxxQkFBTztBQUFBLFlBRVQsS0FBSztBQUNILHFCQUFPO0FBQUEsVUFBQTtBQUlYLGNBQUksT0FBTyxTQUFTLFVBQVU7QUFDNUIsb0JBQVEsS0FBSyxVQUFBO0FBQUEsY0FDWCxLQUFLO0FBQ0gsb0JBQUksVUFBVTtBQUNkLHVCQUFPLGVBQWUsT0FBTyxJQUFJO0FBQUEsY0FFbkMsS0FBSztBQUNILG9CQUFJLFdBQVc7QUFDZix1QkFBTyxlQUFlLFNBQVMsUUFBUSxJQUFJO0FBQUEsY0FFN0MsS0FBSztBQUNILHVCQUFPLGVBQWUsTUFBTSxLQUFLLFFBQVEsWUFBWTtBQUFBLGNBRXZELEtBQUs7QUFDSCxvQkFBSSxZQUFZLEtBQUssZUFBZTtBQUVwQyxvQkFBSSxjQUFjLE1BQU07QUFDdEIseUJBQU87QUFBQSxnQkFBQTtBQUdULHVCQUFPLHlCQUF5QixLQUFLLElBQUksS0FBSztBQUFBLGNBRWhELEtBQUssaUJBQ0g7QUFDRSxvQkFBSSxnQkFBZ0I7QUFDcEIsb0JBQUksVUFBVSxjQUFjO0FBQzVCLG9CQUFJLE9BQU8sY0FBYztBQUV6QixvQkFBSTtBQUNGLHlCQUFPLHlCQUF5QixLQUFLLE9BQU8sQ0FBQztBQUFBLGdCQUFBLFNBQ3RDLEdBQUc7QUFDVix5QkFBTztBQUFBLGdCQUFBO0FBQUEsY0FDVDtBQUFBLFlBQ0Y7QUFBQSxVQUdKO0FBR0YsaUJBQU87QUFBQSxRQUFBO0FBR1QsWUFBSSxTQUFTLE9BQU87QUFNcEIsWUFBSSxnQkFBZ0I7QUFDcEIsWUFBSTtBQUNKLFlBQUk7QUFDSixZQUFJO0FBQ0osWUFBSTtBQUNKLFlBQUk7QUFDSixZQUFJO0FBQ0osWUFBSTtBQUVKLGlCQUFTLGNBQWM7QUFBQSxRQUFBO0FBRXZCLG9CQUFZLHFCQUFxQjtBQUNqQyxpQkFBUyxjQUFjO0FBQ3JCO0FBQ0UsZ0JBQUksa0JBQWtCLEdBQUc7QUFFdkIsd0JBQVUsUUFBUTtBQUNsQix5QkFBVyxRQUFRO0FBQ25CLHlCQUFXLFFBQVE7QUFDbkIsMEJBQVksUUFBUTtBQUNwQiwwQkFBWSxRQUFRO0FBQ3BCLG1DQUFxQixRQUFRO0FBQzdCLDZCQUFlLFFBQVE7QUFFdkIsa0JBQUksUUFBUTtBQUFBLGdCQUNWLGNBQWM7QUFBQSxnQkFDZCxZQUFZO0FBQUEsZ0JBQ1osT0FBTztBQUFBLGdCQUNQLFVBQVU7QUFBQTtBQUdaLHFCQUFPLGlCQUFpQixTQUFTO0FBQUEsZ0JBQy9CLE1BQU07QUFBQSxnQkFDTixLQUFLO0FBQUEsZ0JBQ0wsTUFBTTtBQUFBLGdCQUNOLE9BQU87QUFBQSxnQkFDUCxPQUFPO0FBQUEsZ0JBQ1AsZ0JBQWdCO0FBQUEsZ0JBQ2hCLFVBQVU7QUFBQSxjQUFBLENBQ1g7QUFBQSxZQUFBO0FBSUg7QUFBQSxVQUFBO0FBQUEsUUFDRjtBQUVGLGlCQUFTLGVBQWU7QUFDdEI7QUFDRTtBQUVBLGdCQUFJLGtCQUFrQixHQUFHO0FBRXZCLGtCQUFJLFFBQVE7QUFBQSxnQkFDVixjQUFjO0FBQUEsZ0JBQ2QsWUFBWTtBQUFBLGdCQUNaLFVBQVU7QUFBQTtBQUdaLHFCQUFPLGlCQUFpQixTQUFTO0FBQUEsZ0JBQy9CLEtBQUssT0FBTyxDQUFBLEdBQUksT0FBTztBQUFBLGtCQUNyQixPQUFPO0FBQUEsZ0JBQUEsQ0FDUjtBQUFBLGdCQUNELE1BQU0sT0FBTyxDQUFBLEdBQUksT0FBTztBQUFBLGtCQUN0QixPQUFPO0FBQUEsZ0JBQUEsQ0FDUjtBQUFBLGdCQUNELE1BQU0sT0FBTyxDQUFBLEdBQUksT0FBTztBQUFBLGtCQUN0QixPQUFPO0FBQUEsZ0JBQUEsQ0FDUjtBQUFBLGdCQUNELE9BQU8sT0FBTyxDQUFBLEdBQUksT0FBTztBQUFBLGtCQUN2QixPQUFPO0FBQUEsZ0JBQUEsQ0FDUjtBQUFBLGdCQUNELE9BQU8sT0FBTyxDQUFBLEdBQUksT0FBTztBQUFBLGtCQUN2QixPQUFPO0FBQUEsZ0JBQUEsQ0FDUjtBQUFBLGdCQUNELGdCQUFnQixPQUFPLENBQUEsR0FBSSxPQUFPO0FBQUEsa0JBQ2hDLE9BQU87QUFBQSxnQkFBQSxDQUNSO0FBQUEsZ0JBQ0QsVUFBVSxPQUFPLENBQUEsR0FBSSxPQUFPO0FBQUEsa0JBQzFCLE9BQU87QUFBQSxpQkFDUjtBQUFBLGNBQUEsQ0FDRjtBQUFBLFlBQUE7QUFJSCxnQkFBSSxnQkFBZ0IsR0FBRztBQUNyQixvQkFBTSw4RUFBbUY7QUFBQSxZQUFBO0FBQUEsVUFDM0Y7QUFBQSxRQUNGO0FBR0YsWUFBSSx5QkFBeUIscUJBQXFCO0FBQ2xELFlBQUk7QUFDSixpQkFBUyw4QkFBOEIsTUFBTSxRQUFRLFNBQVM7QUFDNUQ7QUFDRSxnQkFBSSxXQUFXLFFBQVc7QUFFeEIsa0JBQUk7QUFDRixzQkFBTSxNQUFBO0FBQUEsY0FBTSxTQUNMLEdBQUc7QUFDVixvQkFBSSxRQUFRLEVBQUUsTUFBTSxLQUFBLEVBQU8sTUFBTSxjQUFjO0FBQy9DLHlCQUFTLFNBQVMsTUFBTSxDQUFDLEtBQUs7QUFBQSxjQUFBO0FBQUEsWUFDaEM7QUFJRixtQkFBTyxPQUFPLFNBQVM7QUFBQSxVQUFBO0FBQUEsUUFDekI7QUFFRixZQUFJLFVBQVU7QUFDZCxZQUFJO0FBRUo7QUFDRSxjQUFJLGtCQUFrQixPQUFPLFlBQVksYUFBYSxVQUFVO0FBQ2hFLGdDQUFzQixJQUFJLGdCQUFBO0FBQUEsUUFBZ0I7QUFHNUMsaUJBQVMsNkJBQTZCLElBQUksV0FBVztBQUVuRCxjQUFLLENBQUMsTUFBTSxTQUFTO0FBQ25CLG1CQUFPO0FBQUEsVUFBQTtBQUdUO0FBQ0UsZ0JBQUksUUFBUSxvQkFBb0IsSUFBSSxFQUFFO0FBRXRDLGdCQUFJLFVBQVUsUUFBVztBQUN2QixxQkFBTztBQUFBLFlBQUE7QUFBQSxVQUNUO0FBR0YsY0FBSTtBQUNKLG9CQUFVO0FBQ1YsY0FBSSw0QkFBNEIsTUFBTTtBQUV0QyxnQkFBTSxvQkFBb0I7QUFDMUIsY0FBSTtBQUVKO0FBQ0UsaUNBQXFCLHVCQUF1QjtBQUc1QyxtQ0FBdUIsVUFBVTtBQUNqQyx3QkFBQTtBQUFBLFVBQVk7QUFHZCxjQUFJO0FBRUYsZ0JBQUksV0FBVztBQUViLGtCQUFJLE9BQU8sV0FBWTtBQUNyQixzQkFBTSxNQUFBO0FBQUEsY0FBTTtBQUlkLHFCQUFPLGVBQWUsS0FBSyxXQUFXLFNBQVM7QUFBQSxnQkFDN0MsS0FBSyxXQUFZO0FBR2Ysd0JBQU0sTUFBQTtBQUFBLGdCQUFNO0FBQUEsY0FDZCxDQUNEO0FBRUQsa0JBQUksT0FBTyxZQUFZLFlBQVksUUFBUSxXQUFXO0FBR3BELG9CQUFJO0FBQ0YsMEJBQVEsVUFBVSxNQUFNLEVBQUU7QUFBQSxnQkFBQSxTQUNuQixHQUFHO0FBQ1YsNEJBQVU7QUFBQSxnQkFBQTtBQUdaLHdCQUFRLFVBQVUsSUFBSSxDQUFBLEdBQUksSUFBSTtBQUFBLGNBQUEsT0FDekI7QUFDTCxvQkFBSTtBQUNGLHVCQUFLLEtBQUE7QUFBQSxnQkFBSyxTQUNILEdBQUc7QUFDViw0QkFBVTtBQUFBLGdCQUFBO0FBR1osbUJBQUcsS0FBSyxLQUFLLFNBQVM7QUFBQSxjQUFBO0FBQUEsWUFDeEIsT0FDSztBQUNMLGtCQUFJO0FBQ0Ysc0JBQU0sTUFBQTtBQUFBLGNBQU0sU0FDTCxHQUFHO0FBQ1YsMEJBQVU7QUFBQSxjQUFBO0FBR1osaUJBQUE7QUFBQSxZQUFHO0FBQUEsVUFDTCxTQUNPLFFBQVE7QUFFZixnQkFBSSxVQUFVLFdBQVcsT0FBTyxPQUFPLFVBQVUsVUFBVTtBQUd6RCxrQkFBSSxjQUFjLE9BQU8sTUFBTSxNQUFNLElBQUk7QUFDekMsa0JBQUksZUFBZSxRQUFRLE1BQU0sTUFBTSxJQUFJO0FBQzNDLGtCQUFJLElBQUksWUFBWSxTQUFTO0FBQzdCLGtCQUFJLElBQUksYUFBYSxTQUFTO0FBRTlCLHFCQUFPLEtBQUssS0FBSyxLQUFLLEtBQUssWUFBWSxDQUFDLE1BQU0sYUFBYSxDQUFDLEdBQUc7QUFPN0Q7QUFBQSxjQUFBO0FBR0YscUJBQU8sS0FBSyxLQUFLLEtBQUssR0FBRyxLQUFLLEtBQUs7QUFHakMsb0JBQUksWUFBWSxDQUFDLE1BQU0sYUFBYSxDQUFDLEdBQUc7QUFNdEMsc0JBQUksTUFBTSxLQUFLLE1BQU0sR0FBRztBQUN0Qix1QkFBRztBQUNEO0FBQ0E7QUFHQSwwQkFBSSxJQUFJLEtBQUssWUFBWSxDQUFDLE1BQU0sYUFBYSxDQUFDLEdBQUc7QUFFL0MsNEJBQUksU0FBUyxPQUFPLFlBQVksQ0FBQyxFQUFFLFFBQVEsWUFBWSxNQUFNO0FBSzdELDRCQUFJLEdBQUcsZUFBZSxPQUFPLFNBQVMsYUFBYSxHQUFHO0FBQ3BELG1DQUFTLE9BQU8sUUFBUSxlQUFlLEdBQUcsV0FBVztBQUFBLHdCQUFBO0FBR3ZEO0FBQ0UsOEJBQUksT0FBTyxPQUFPLFlBQVk7QUFDNUIsZ0RBQW9CLElBQUksSUFBSSxNQUFNO0FBQUEsMEJBQUE7QUFBQSx3QkFDcEM7QUFJRiwrQkFBTztBQUFBLHNCQUFBO0FBQUEsb0JBQ1QsU0FDTyxLQUFLLEtBQUssS0FBSztBQUFBLGtCQUFBO0FBRzFCO0FBQUEsZ0JBQUE7QUFBQSxjQUNGO0FBQUEsWUFDRjtBQUFBLFVBQ0YsVUFDRjtBQUNFLHNCQUFVO0FBRVY7QUFDRSxxQ0FBdUIsVUFBVTtBQUNqQywyQkFBQTtBQUFBLFlBQWE7QUFHZixrQkFBTSxvQkFBb0I7QUFBQSxVQUFBO0FBSTVCLGNBQUksT0FBTyxLQUFLLEdBQUcsZUFBZSxHQUFHLE9BQU87QUFDNUMsY0FBSSxpQkFBaUIsT0FBTyw4QkFBOEIsSUFBSSxJQUFJO0FBRWxFO0FBQ0UsZ0JBQUksT0FBTyxPQUFPLFlBQVk7QUFDNUIsa0NBQW9CLElBQUksSUFBSSxjQUFjO0FBQUEsWUFBQTtBQUFBLFVBQzVDO0FBR0YsaUJBQU87QUFBQSxRQUFBO0FBRVQsaUJBQVMsK0JBQStCLElBQUksUUFBUSxTQUFTO0FBQzNEO0FBQ0UsbUJBQU8sNkJBQTZCLElBQUksS0FBSztBQUFBLFVBQUE7QUFBQSxRQUMvQztBQUdGLGlCQUFTLGdCQUFnQixXQUFXO0FBQ2xDLGNBQUksWUFBWSxVQUFVO0FBQzFCLGlCQUFPLENBQUMsRUFBRSxhQUFhLFVBQVU7QUFBQSxRQUFBO0FBR25DLGlCQUFTLHFDQUFxQyxNQUFNLFFBQVEsU0FBUztBQUVuRSxjQUFJLFFBQVEsTUFBTTtBQUNoQixtQkFBTztBQUFBLFVBQUE7QUFHVCxjQUFJLE9BQU8sU0FBUyxZQUFZO0FBQzlCO0FBQ0UscUJBQU8sNkJBQTZCLE1BQU0sZ0JBQWdCLElBQUksQ0FBQztBQUFBLFlBQUE7QUFBQSxVQUNqRTtBQUdGLGNBQUksT0FBTyxTQUFTLFVBQVU7QUFDNUIsbUJBQU8sOEJBQThCLElBQUk7QUFBQSxVQUFBO0FBRzNDLGtCQUFRLE1BQUE7QUFBQSxZQUNOLEtBQUs7QUFDSCxxQkFBTyw4QkFBOEIsVUFBVTtBQUFBLFlBRWpELEtBQUs7QUFDSCxxQkFBTyw4QkFBOEIsY0FBYztBQUFBLFVBQUE7QUFHdkQsY0FBSSxPQUFPLFNBQVMsVUFBVTtBQUM1QixvQkFBUSxLQUFLLFVBQUE7QUFBQSxjQUNYLEtBQUs7QUFDSCx1QkFBTywrQkFBK0IsS0FBSyxNQUFNO0FBQUEsY0FFbkQsS0FBSztBQUVILHVCQUFPLHFDQUFxQyxLQUFLLE1BQU0sUUFBUSxPQUFPO0FBQUEsY0FFeEUsS0FBSyxpQkFDSDtBQUNFLG9CQUFJLGdCQUFnQjtBQUNwQixvQkFBSSxVQUFVLGNBQWM7QUFDNUIsb0JBQUksT0FBTyxjQUFjO0FBRXpCLG9CQUFJO0FBRUYseUJBQU8scUNBQXFDLEtBQUssT0FBTyxHQUFHLFFBQVEsT0FBTztBQUFBLGdCQUFBLFNBQ25FLEdBQUc7QUFBQSxnQkFBQTtBQUFBLGNBQUM7QUFBQSxZQUNmO0FBQUEsVUFDSjtBQUdGLGlCQUFPO0FBQUEsUUFBQTtBQUdULFlBQUksaUJBQWlCLE9BQU8sVUFBVTtBQUV0QyxZQUFJLHFCQUFxQixDQUFBO0FBQ3pCLFlBQUkseUJBQXlCLHFCQUFxQjtBQUVsRCxpQkFBUyw4QkFBOEIsU0FBUztBQUM5QztBQUNFLGdCQUFJLFNBQVM7QUFDWCxrQkFBSSxRQUFRLFFBQVE7QUFDcEIsa0JBQUksUUFBUSxxQ0FBcUMsUUFBUSxNQUFNLFFBQVEsU0FBUyxRQUFRLE1BQU0sT0FBTyxJQUFJO0FBQ3pHLHFDQUF1QixtQkFBbUIsS0FBSztBQUFBLFlBQUEsT0FDMUM7QUFDTCxxQ0FBdUIsbUJBQW1CLElBQUk7QUFBQSxZQUFBO0FBQUEsVUFDaEQ7QUFBQSxRQUNGO0FBR0YsaUJBQVMsZUFBZSxXQUFXLFFBQVEsVUFBVSxlQUFlLFNBQVM7QUFDM0U7QUFFRSxnQkFBSSxNQUFNLFNBQVMsS0FBSyxLQUFLLGNBQWM7QUFFM0MscUJBQVMsZ0JBQWdCLFdBQVc7QUFDbEMsa0JBQUksSUFBSSxXQUFXLFlBQVksR0FBRztBQUNoQyxvQkFBSSxVQUFVO0FBSWQsb0JBQUk7QUFHRixzQkFBSSxPQUFPLFVBQVUsWUFBWSxNQUFNLFlBQVk7QUFFakQsd0JBQUksTUFBTSxPQUFPLGlCQUFpQixpQkFBaUIsT0FBTyxXQUFXLFlBQVksZUFBZSwrRkFBb0csT0FBTyxVQUFVLFlBQVksSUFBSSxpR0FBc0c7QUFDM1Usd0JBQUksT0FBTztBQUNYLDBCQUFNO0FBQUEsa0JBQUE7QUFHUiw0QkFBVSxVQUFVLFlBQVksRUFBRSxRQUFRLGNBQWMsZUFBZSxVQUFVLE1BQU0sOENBQThDO0FBQUEsZ0JBQUEsU0FDOUgsSUFBSTtBQUNYLDRCQUFVO0FBQUEsZ0JBQUE7QUFHWixvQkFBSSxXQUFXLEVBQUUsbUJBQW1CLFFBQVE7QUFDMUMsZ0RBQThCLE9BQU87QUFFckMsd0JBQU0sNFJBQXFULGlCQUFpQixlQUFlLFVBQVUsY0FBYyxPQUFPLE9BQU87QUFFalksZ0RBQThCLElBQUk7QUFBQSxnQkFBQTtBQUdwQyxvQkFBSSxtQkFBbUIsU0FBUyxFQUFFLFFBQVEsV0FBVyxxQkFBcUI7QUFHeEUscUNBQW1CLFFBQVEsT0FBTyxJQUFJO0FBQ3RDLGdEQUE4QixPQUFPO0FBRXJDLHdCQUFNLHNCQUFzQixVQUFVLFFBQVEsT0FBTztBQUVyRCxnREFBOEIsSUFBSTtBQUFBLGdCQUFBO0FBQUEsY0FDcEM7QUFBQSxZQUNGO0FBQUEsVUFDRjtBQUFBLFFBQ0Y7QUFHRixZQUFJLGNBQWMsTUFBTTtBQUV4QixpQkFBUyxRQUFRLEdBQUc7QUFDbEIsaUJBQU8sWUFBWSxDQUFDO0FBQUEsUUFBQTtBQWF0QixpQkFBUyxTQUFTLE9BQU87QUFDdkI7QUFFRSxnQkFBSSxpQkFBaUIsT0FBTyxXQUFXLGNBQWMsT0FBTztBQUM1RCxnQkFBSSxPQUFPLGtCQUFrQixNQUFNLE9BQU8sV0FBVyxLQUFLLE1BQU0sWUFBWSxRQUFRO0FBQ3BGLG1CQUFPO0FBQUEsVUFBQTtBQUFBLFFBQ1Q7QUFJRixpQkFBUyxrQkFBa0IsT0FBTztBQUNoQztBQUNFLGdCQUFJO0FBQ0YsaUNBQW1CLEtBQUs7QUFDeEIscUJBQU87QUFBQSxZQUFBLFNBQ0EsR0FBRztBQUNWLHFCQUFPO0FBQUEsWUFBQTtBQUFBLFVBQ1Q7QUFBQSxRQUNGO0FBR0YsaUJBQVMsbUJBQW1CLE9BQU87QUF3QmpDLGlCQUFPLEtBQUs7QUFBQSxRQUFBO0FBRWQsaUJBQVMsdUJBQXVCLE9BQU87QUFDckM7QUFDRSxnQkFBSSxrQkFBa0IsS0FBSyxHQUFHO0FBQzVCLG9CQUFNLG1IQUF3SCxTQUFTLEtBQUssQ0FBQztBQUU3SSxxQkFBTyxtQkFBbUIsS0FBSztBQUFBLFlBQUE7QUFBQSxVQUNqQztBQUFBLFFBQ0Y7QUFHRixZQUFJLG9CQUFvQixxQkFBcUI7QUFDN0MsWUFBSSxpQkFBaUI7QUFBQSxVQUNuQixLQUFLO0FBQUEsVUFDTCxLQUFLO0FBQUEsVUFDTCxRQUFRO0FBQUEsVUFDUixVQUFVO0FBQUE7QUFFWixZQUFJO0FBQ0osWUFBSTtBQU9KLGlCQUFTLFlBQVksUUFBUTtBQUMzQjtBQUNFLGdCQUFJLGVBQWUsS0FBSyxRQUFRLEtBQUssR0FBRztBQUN0QyxrQkFBSSxTQUFTLE9BQU8seUJBQXlCLFFBQVEsS0FBSyxFQUFFO0FBRTVELGtCQUFJLFVBQVUsT0FBTyxnQkFBZ0I7QUFDbkMsdUJBQU87QUFBQSxjQUFBO0FBQUEsWUFDVDtBQUFBLFVBQ0Y7QUFHRixpQkFBTyxPQUFPLFFBQVE7QUFBQSxRQUFBO0FBR3hCLGlCQUFTLFlBQVksUUFBUTtBQUMzQjtBQUNFLGdCQUFJLGVBQWUsS0FBSyxRQUFRLEtBQUssR0FBRztBQUN0QyxrQkFBSSxTQUFTLE9BQU8seUJBQXlCLFFBQVEsS0FBSyxFQUFFO0FBRTVELGtCQUFJLFVBQVUsT0FBTyxnQkFBZ0I7QUFDbkMsdUJBQU87QUFBQSxjQUFBO0FBQUEsWUFDVDtBQUFBLFVBQ0Y7QUFHRixpQkFBTyxPQUFPLFFBQVE7QUFBQSxRQUFBO0FBR3hCLGlCQUFTLHFDQUFxQyxRQUFRQyxPQUFNO0FBQzFEO0FBQ0UsZ0JBQUksT0FBTyxPQUFPLFFBQVEsWUFBWSxrQkFBa0IsV0FBV0EsTUFBc0Q7QUFBQSxVQVF6SDtBQUFBLFFBQ0Y7QUFHRixpQkFBUywyQkFBMkIsT0FBTyxhQUFhO0FBQ3REO0FBQ0UsZ0JBQUksd0JBQXdCLFdBQVk7QUFDdEMsa0JBQUksQ0FBQyw0QkFBNEI7QUFDL0IsNkNBQTZCO0FBRTdCLHNCQUFNLDZPQUE0UCxXQUFXO0FBQUEsY0FBQTtBQUFBLFlBQy9RO0FBR0Ysa0NBQXNCLGlCQUFpQjtBQUN2QyxtQkFBTyxlQUFlLE9BQU8sT0FBTztBQUFBLGNBQ2xDLEtBQUs7QUFBQSxjQUNMLGNBQWM7QUFBQSxZQUFBLENBQ2Y7QUFBQSxVQUFBO0FBQUEsUUFDSDtBQUdGLGlCQUFTLDJCQUEyQixPQUFPLGFBQWE7QUFDdEQ7QUFDRSxnQkFBSSx3QkFBd0IsV0FBWTtBQUN0QyxrQkFBSSxDQUFDLDRCQUE0QjtBQUMvQiw2Q0FBNkI7QUFFN0Isc0JBQU0sNk9BQTRQLFdBQVc7QUFBQSxjQUFBO0FBQUEsWUFDL1E7QUFHRixrQ0FBc0IsaUJBQWlCO0FBQ3ZDLG1CQUFPLGVBQWUsT0FBTyxPQUFPO0FBQUEsY0FDbEMsS0FBSztBQUFBLGNBQ0wsY0FBYztBQUFBLFlBQUEsQ0FDZjtBQUFBLFVBQUE7QUFBQSxRQUNIO0FBd0JGLFlBQUksZUFBZSxTQUFVLE1BQU0sS0FBSyxLQUFLQSxPQUFNLFFBQVEsT0FBTyxPQUFPO0FBQ3ZFLGNBQUksVUFBVTtBQUFBO0FBQUEsWUFFWixVQUFVO0FBQUE7QUFBQSxZQUVWO0FBQUEsWUFDQTtBQUFBLFlBQ0E7QUFBQSxZQUNBO0FBQUE7QUFBQSxZQUVBLFFBQVE7QUFBQTtBQUdWO0FBS0Usb0JBQVEsU0FBUyxDQUFBO0FBS2pCLG1CQUFPLGVBQWUsUUFBUSxRQUFRLGFBQWE7QUFBQSxjQUNqRCxjQUFjO0FBQUEsY0FDZCxZQUFZO0FBQUEsY0FDWixVQUFVO0FBQUEsY0FDVixPQUFPO0FBQUEsWUFBQSxDQUNSO0FBRUQsbUJBQU8sZUFBZSxTQUFTLFNBQVM7QUFBQSxjQUN0QyxjQUFjO0FBQUEsY0FDZCxZQUFZO0FBQUEsY0FDWixVQUFVO0FBQUEsY0FDVixPQUFPQTtBQUFBLFlBQUEsQ0FDUjtBQUdELG1CQUFPLGVBQWUsU0FBUyxXQUFXO0FBQUEsY0FDeEMsY0FBYztBQUFBLGNBQ2QsWUFBWTtBQUFBLGNBQ1osVUFBVTtBQUFBLGNBQ1YsT0FBTztBQUFBLFlBQUEsQ0FDUjtBQUVELGdCQUFJLE9BQU8sUUFBUTtBQUNqQixxQkFBTyxPQUFPLFFBQVEsS0FBSztBQUMzQixxQkFBTyxPQUFPLE9BQU87QUFBQSxZQUFBO0FBQUEsVUFDdkI7QUFHRixpQkFBTztBQUFBLFFBQUE7QUFTVCxpQkFBUyxPQUFPLE1BQU0sUUFBUSxVQUFVLFFBQVFBLE9BQU07QUFDcEQ7QUFDRSxnQkFBSTtBQUVKLGdCQUFJLFFBQVEsQ0FBQTtBQUNaLGdCQUFJLE1BQU07QUFDVixnQkFBSSxNQUFNO0FBT1YsZ0JBQUksYUFBYSxRQUFXO0FBQzFCO0FBQ0UsdUNBQXVCLFFBQVE7QUFBQSxjQUFBO0FBR2pDLG9CQUFNLEtBQUs7QUFBQSxZQUFBO0FBR2IsZ0JBQUksWUFBWSxNQUFNLEdBQUc7QUFDdkI7QUFDRSx1Q0FBdUIsT0FBTyxHQUFHO0FBQUEsY0FBQTtBQUduQyxvQkFBTSxLQUFLLE9BQU87QUFBQSxZQUFBO0FBR3BCLGdCQUFJLFlBQVksTUFBTSxHQUFHO0FBQ3ZCLG9CQUFNLE9BQU87QUFDYixtREFBcUMsUUFBUUEsS0FBSTtBQUFBLFlBQUE7QUFJbkQsaUJBQUssWUFBWSxRQUFRO0FBQ3ZCLGtCQUFJLGVBQWUsS0FBSyxRQUFRLFFBQVEsS0FBSyxDQUFDLGVBQWUsZUFBZSxRQUFRLEdBQUc7QUFDckYsc0JBQU0sUUFBUSxJQUFJLE9BQU8sUUFBUTtBQUFBLGNBQUE7QUFBQSxZQUNuQztBQUlGLGdCQUFJLFFBQVEsS0FBSyxjQUFjO0FBQzdCLGtCQUFJLGVBQWUsS0FBSztBQUV4QixtQkFBSyxZQUFZLGNBQWM7QUFDN0Isb0JBQUksTUFBTSxRQUFRLE1BQU0sUUFBVztBQUNqQyx3QkFBTSxRQUFRLElBQUksYUFBYSxRQUFRO0FBQUEsZ0JBQUE7QUFBQSxjQUN6QztBQUFBLFlBQ0Y7QUFHRixnQkFBSSxPQUFPLEtBQUs7QUFDZCxrQkFBSSxjQUFjLE9BQU8sU0FBUyxhQUFhLEtBQUssZUFBZSxLQUFLLFFBQVEsWUFBWTtBQUU1RixrQkFBSSxLQUFLO0FBQ1AsMkNBQTJCLE9BQU8sV0FBVztBQUFBLGNBQUE7QUFHL0Msa0JBQUksS0FBSztBQUNQLDJDQUEyQixPQUFPLFdBQVc7QUFBQSxjQUFBO0FBQUEsWUFDL0M7QUFHRixtQkFBTyxhQUFhLE1BQU0sS0FBSyxLQUFLQSxPQUFNLFFBQVEsa0JBQWtCLFNBQVMsS0FBSztBQUFBLFVBQUE7QUFBQSxRQUNwRjtBQUdGLFlBQUksc0JBQXNCLHFCQUFxQjtBQUMvQyxZQUFJLDJCQUEyQixxQkFBcUI7QUFFcEQsaUJBQVMsZ0NBQWdDLFNBQVM7QUFDaEQ7QUFDRSxnQkFBSSxTQUFTO0FBQ1gsa0JBQUksUUFBUSxRQUFRO0FBQ3BCLGtCQUFJLFFBQVEscUNBQXFDLFFBQVEsTUFBTSxRQUFRLFNBQVMsUUFBUSxNQUFNLE9BQU8sSUFBSTtBQUN6Ryx1Q0FBeUIsbUJBQW1CLEtBQUs7QUFBQSxZQUFBLE9BQzVDO0FBQ0wsdUNBQXlCLG1CQUFtQixJQUFJO0FBQUEsWUFBQTtBQUFBLFVBQ2xEO0FBQUEsUUFDRjtBQUdGLFlBQUk7QUFFSjtBQUNFLDBDQUFnQztBQUFBLFFBQUE7QUFXbEMsaUJBQVMsZUFBZSxRQUFRO0FBQzlCO0FBQ0UsbUJBQU8sT0FBTyxXQUFXLFlBQVksV0FBVyxRQUFRLE9BQU8sYUFBYTtBQUFBLFVBQUE7QUFBQSxRQUM5RTtBQUdGLGlCQUFTLDhCQUE4QjtBQUNyQztBQUNFLGdCQUFJLG9CQUFvQixTQUFTO0FBQy9CLGtCQUFJLE9BQU8seUJBQXlCLG9CQUFvQixRQUFRLElBQUk7QUFFcEUsa0JBQUksTUFBTTtBQUNSLHVCQUFPLHFDQUFxQyxPQUFPO0FBQUEsY0FBQTtBQUFBLFlBQ3JEO0FBR0YsbUJBQU87QUFBQSxVQUFBO0FBQUEsUUFDVDtBQUdGLGlCQUFTLDJCQUEyQixRQUFRO0FBQzFDO0FBT0UsbUJBQU87QUFBQSxVQUFBO0FBQUEsUUFDVDtBQVNGLFlBQUksd0JBQXdCLENBQUE7QUFFNUIsaUJBQVMsNkJBQTZCLFlBQVk7QUFDaEQ7QUFDRSxnQkFBSSxPQUFPLDRCQUFBO0FBRVgsZ0JBQUksQ0FBQyxNQUFNO0FBQ1Qsa0JBQUksYUFBYSxPQUFPLGVBQWUsV0FBVyxhQUFhLFdBQVcsZUFBZSxXQUFXO0FBRXBHLGtCQUFJLFlBQVk7QUFDZCx1QkFBTyxnREFBZ0QsYUFBYTtBQUFBLGNBQUE7QUFBQSxZQUN0RTtBQUdGLG1CQUFPO0FBQUEsVUFBQTtBQUFBLFFBQ1Q7QUFlRixpQkFBUyxvQkFBb0IsU0FBUyxZQUFZO0FBQ2hEO0FBQ0UsZ0JBQUksQ0FBQyxRQUFRLFVBQVUsUUFBUSxPQUFPLGFBQWEsUUFBUSxPQUFPLE1BQU07QUFDdEU7QUFBQSxZQUFBO0FBR0Ysb0JBQVEsT0FBTyxZQUFZO0FBQzNCLGdCQUFJLDRCQUE0Qiw2QkFBNkIsVUFBVTtBQUV2RSxnQkFBSSxzQkFBc0IseUJBQXlCLEdBQUc7QUFDcEQ7QUFBQSxZQUFBO0FBR0Ysa0NBQXNCLHlCQUF5QixJQUFJO0FBSW5ELGdCQUFJLGFBQWE7QUFFakIsZ0JBQUksV0FBVyxRQUFRLFVBQVUsUUFBUSxXQUFXLG9CQUFvQixTQUFTO0FBRS9FLDJCQUFhLGlDQUFpQyx5QkFBeUIsUUFBUSxPQUFPLElBQUksSUFBSTtBQUFBLFlBQUE7QUFHaEcsNENBQWdDLE9BQU87QUFFdkMsa0JBQU0sNkhBQWtJLDJCQUEyQixVQUFVO0FBRTdLLDRDQUFnQyxJQUFJO0FBQUEsVUFBQTtBQUFBLFFBQ3RDO0FBYUYsaUJBQVMsa0JBQWtCLE1BQU0sWUFBWTtBQUMzQztBQUNFLGdCQUFJLE9BQU8sU0FBUyxVQUFVO0FBQzVCO0FBQUEsWUFBQTtBQUdGLGdCQUFJLFFBQVEsSUFBSSxHQUFHO0FBQ2pCLHVCQUFTLElBQUksR0FBRyxJQUFJLEtBQUssUUFBUSxLQUFLO0FBQ3BDLG9CQUFJLFFBQVEsS0FBSyxDQUFDO0FBRWxCLG9CQUFJLGVBQWUsS0FBSyxHQUFHO0FBQ3pCLHNDQUFvQixPQUFPLFVBQVU7QUFBQSxnQkFBQTtBQUFBLGNBQ3ZDO0FBQUEsWUFDRixXQUNTLGVBQWUsSUFBSSxHQUFHO0FBRS9CLGtCQUFJLEtBQUssUUFBUTtBQUNmLHFCQUFLLE9BQU8sWUFBWTtBQUFBLGNBQUE7QUFBQSxZQUMxQixXQUNTLE1BQU07QUFDZixrQkFBSSxhQUFhLGNBQWMsSUFBSTtBQUVuQyxrQkFBSSxPQUFPLGVBQWUsWUFBWTtBQUdwQyxvQkFBSSxlQUFlLEtBQUssU0FBUztBQUMvQixzQkFBSSxXQUFXLFdBQVcsS0FBSyxJQUFJO0FBQ25DLHNCQUFJO0FBRUoseUJBQU8sRUFBRSxPQUFPLFNBQVMsS0FBQSxHQUFRLE1BQU07QUFDckMsd0JBQUksZUFBZSxLQUFLLEtBQUssR0FBRztBQUM5QiwwQ0FBb0IsS0FBSyxPQUFPLFVBQVU7QUFBQSxvQkFBQTtBQUFBLGtCQUM1QztBQUFBLGdCQUNGO0FBQUEsY0FDRjtBQUFBLFlBQ0Y7QUFBQSxVQUNGO0FBQUEsUUFDRjtBQVVGLGlCQUFTLGtCQUFrQixTQUFTO0FBQ2xDO0FBQ0UsZ0JBQUksT0FBTyxRQUFRO0FBRW5CLGdCQUFJLFNBQVMsUUFBUSxTQUFTLFVBQWEsT0FBTyxTQUFTLFVBQVU7QUFDbkU7QUFBQSxZQUFBO0FBR0YsZ0JBQUk7QUFFSixnQkFBSSxPQUFPLFNBQVMsWUFBWTtBQUM5QiwwQkFBWSxLQUFLO0FBQUEsWUFBQSxXQUNSLE9BQU8sU0FBUyxhQUFhLEtBQUssYUFBYTtBQUFBO0FBQUEsWUFFMUQsS0FBSyxhQUFhLGtCQUFrQjtBQUNsQywwQkFBWSxLQUFLO0FBQUEsWUFBQSxPQUNaO0FBQ0w7QUFBQSxZQUFBO0FBR0YsZ0JBQUksV0FBVztBQUViLGtCQUFJLE9BQU8seUJBQXlCLElBQUk7QUFDeEMsNkJBQWUsV0FBVyxRQUFRLE9BQU8sUUFBUSxNQUFNLE9BQU87QUFBQSxZQUFBLFdBQ3JELEtBQUssY0FBYyxVQUFhLENBQUMsK0JBQStCO0FBQ3pFLDhDQUFnQztBQUVoQyxrQkFBSSxRQUFRLHlCQUF5QixJQUFJO0FBRXpDLG9CQUFNLHVHQUF1RyxTQUFTLFNBQVM7QUFBQSxZQUFBO0FBR2pJLGdCQUFJLE9BQU8sS0FBSyxvQkFBb0IsY0FBYyxDQUFDLEtBQUssZ0JBQWdCLHNCQUFzQjtBQUM1RixvQkFBTSw0SEFBaUk7QUFBQSxZQUFBO0FBQUEsVUFDekk7QUFBQSxRQUNGO0FBUUYsaUJBQVMsc0JBQXNCLFVBQVU7QUFDdkM7QUFDRSxnQkFBSSxPQUFPLE9BQU8sS0FBSyxTQUFTLEtBQUs7QUFFckMscUJBQVMsSUFBSSxHQUFHLElBQUksS0FBSyxRQUFRLEtBQUs7QUFDcEMsa0JBQUksTUFBTSxLQUFLLENBQUM7QUFFaEIsa0JBQUksUUFBUSxjQUFjLFFBQVEsT0FBTztBQUN2QyxnREFBZ0MsUUFBUTtBQUV4QyxzQkFBTSw0R0FBaUgsR0FBRztBQUUxSCxnREFBZ0MsSUFBSTtBQUNwQztBQUFBLGNBQUE7QUFBQSxZQUNGO0FBR0YsZ0JBQUksU0FBUyxRQUFRLE1BQU07QUFDekIsOENBQWdDLFFBQVE7QUFFeEMsb0JBQU0sdURBQXVEO0FBRTdELDhDQUFnQyxJQUFJO0FBQUEsWUFBQTtBQUFBLFVBQ3RDO0FBQUEsUUFDRjtBQUdGLFlBQUksd0JBQXdCLENBQUE7QUFDNUIsaUJBQVMsa0JBQWtCLE1BQU0sT0FBTyxLQUFLLGtCQUFrQixRQUFRQSxPQUFNO0FBQzNFO0FBQ0UsZ0JBQUksWUFBWSxtQkFBbUIsSUFBSTtBQUd2QyxnQkFBSSxDQUFDLFdBQVc7QUFDZCxrQkFBSSxPQUFPO0FBRVgsa0JBQUksU0FBUyxVQUFhLE9BQU8sU0FBUyxZQUFZLFNBQVMsUUFBUSxPQUFPLEtBQUssSUFBSSxFQUFFLFdBQVcsR0FBRztBQUNyRyx3QkFBUTtBQUFBLGNBQUE7QUFHVixrQkFBSSxhQUFhLDJCQUFpQztBQUVsRCxrQkFBSSxZQUFZO0FBQ2Qsd0JBQVE7QUFBQSxjQUFBLE9BQ0g7QUFDTCx3QkFBUSw0QkFBQTtBQUFBLGNBQTRCO0FBR3RDLGtCQUFJO0FBRUosa0JBQUksU0FBUyxNQUFNO0FBQ2pCLDZCQUFhO0FBQUEsY0FBQSxXQUNKLFFBQVEsSUFBSSxHQUFHO0FBQ3hCLDZCQUFhO0FBQUEsY0FBQSxXQUNKLFNBQVMsVUFBYSxLQUFLLGFBQWEsb0JBQW9CO0FBQ3JFLDZCQUFhLE9BQU8seUJBQXlCLEtBQUssSUFBSSxLQUFLLGFBQWE7QUFDeEUsdUJBQU87QUFBQSxjQUFBLE9BQ0Y7QUFDTCw2QkFBYSxPQUFPO0FBQUEsY0FBQTtBQUd0QixvQkFBTSwySUFBcUosWUFBWSxJQUFJO0FBQUEsWUFBQTtBQUc3SyxnQkFBSSxVQUFVLE9BQU8sTUFBTSxPQUFPLEtBQUssUUFBUUEsS0FBSTtBQUduRCxnQkFBSSxXQUFXLE1BQU07QUFDbkIscUJBQU87QUFBQSxZQUFBO0FBUVQsZ0JBQUksV0FBVztBQUNiLGtCQUFJLFdBQVcsTUFBTTtBQUVyQixrQkFBSSxhQUFhLFFBQVc7QUFDMUIsb0JBQUksa0JBQWtCO0FBQ3BCLHNCQUFJLFFBQVEsUUFBUSxHQUFHO0FBQ3JCLDZCQUFTLElBQUksR0FBRyxJQUFJLFNBQVMsUUFBUSxLQUFLO0FBQ3hDLHdDQUFrQixTQUFTLENBQUMsR0FBRyxJQUFJO0FBQUEsb0JBQUE7QUFHckMsd0JBQUksT0FBTyxRQUFRO0FBQ2pCLDZCQUFPLE9BQU8sUUFBUTtBQUFBLG9CQUFBO0FBQUEsa0JBQ3hCLE9BQ0s7QUFDTCwwQkFBTSxzSkFBZ0s7QUFBQSxrQkFBQTtBQUFBLGdCQUN4SyxPQUNLO0FBQ0wsb0NBQWtCLFVBQVUsSUFBSTtBQUFBLGdCQUFBO0FBQUEsY0FDbEM7QUFBQSxZQUNGO0FBR0Y7QUFDRSxrQkFBSSxlQUFlLEtBQUssT0FBTyxLQUFLLEdBQUc7QUFDckMsb0JBQUksZ0JBQWdCLHlCQUF5QixJQUFJO0FBQ2pELG9CQUFJLE9BQU8sT0FBTyxLQUFLLEtBQUssRUFBRSxPQUFPLFNBQVUsR0FBRztBQUNoRCx5QkFBTyxNQUFNO0FBQUEsZ0JBQUEsQ0FDZDtBQUNELG9CQUFJLGdCQUFnQixLQUFLLFNBQVMsSUFBSSxvQkFBb0IsS0FBSyxLQUFLLFNBQVMsSUFBSSxXQUFXO0FBRTVGLG9CQUFJLENBQUMsc0JBQXNCLGdCQUFnQixhQUFhLEdBQUc7QUFDekQsc0JBQUksZUFBZSxLQUFLLFNBQVMsSUFBSSxNQUFNLEtBQUssS0FBSyxTQUFTLElBQUksV0FBVztBQUU3RSx3QkFBTSxtT0FBNFAsZUFBZSxlQUFlLGNBQWMsYUFBYTtBQUUzVCx3Q0FBc0IsZ0JBQWdCLGFBQWEsSUFBSTtBQUFBLGdCQUFBO0FBQUEsY0FDekQ7QUFBQSxZQUNGO0FBR0YsZ0JBQUksU0FBUyxxQkFBcUI7QUFDaEMsb0NBQXNCLE9BQU87QUFBQSxZQUFBLE9BQ3hCO0FBQ0wsZ0NBQWtCLE9BQU87QUFBQSxZQUFBO0FBRzNCLG1CQUFPO0FBQUEsVUFBQTtBQUFBLFFBQ1Q7QUFNRixpQkFBUyx3QkFBd0IsTUFBTSxPQUFPLEtBQUs7QUFDakQ7QUFDRSxtQkFBTyxrQkFBa0IsTUFBTSxPQUFPLEtBQUssSUFBSTtBQUFBLFVBQUE7QUFBQSxRQUNqRDtBQUVGLGlCQUFTLHlCQUF5QixNQUFNLE9BQU8sS0FBSztBQUNsRDtBQUNFLG1CQUFPLGtCQUFrQixNQUFNLE9BQU8sS0FBSyxLQUFLO0FBQUEsVUFBQTtBQUFBLFFBQ2xEO0FBR0YsWUFBSSxNQUFPO0FBR1gsWUFBSSxPQUFRO0FBRVosb0NBQUEsV0FBbUI7QUFDbkIsb0NBQUEsTUFBYztBQUNkLG9DQUFBLE9BQWU7QUFBQSxNQUFBLEdBQ2I7QUFBQSxJQUNGOzs7Ozs7O0FDaHpDTztBQUNMQyxpQkFBQSxVQUFpQkgsbUNBQUE7QUFBQSxJQUNuQjs7OztBQ0pPLFFBQU0sZ0NBQWdDLE1BQU07QUFDL0MsVUFBTSwwQkFBMEIsb0JBQUksSUFBRztBQUN2QyxVQUFNLDhCQUE4QixvQkFBSSxJQUFHO0FBQzNDLFVBQU0sb0JBQW9CLENBQUMsV0FBVyxlQUFlLGtCQUFrQjtBQUNuRSxrQ0FBNEIsSUFBSSxXQUFXLGFBQWE7QUFDeEQsOEJBQXdCLElBQUksZUFBZTtBQUFBLFFBQ3ZDLGtCQUFrQixJQUFJLElBQUksYUFBYTtBQUFBLFFBQ3ZDLG9CQUFvQjtBQUFBLE1BQ2hDLENBQVM7QUFDRCxhQUFPO0FBQUEsSUFDWDtBQUNBLFdBQU87QUFBQSxNQUNILGtCQUFrQixDQUFDLGNBQWM7QUFDN0IsY0FBTSxnQkFBZ0IsNEJBQTRCLElBQUksU0FBUztBQUMvRCxZQUFJLENBQUMsZUFBZTtBQUNoQixpQkFBTztBQUFBLFFBQ1g7QUFDQSxlQUFPO0FBQUEsTUFDWDtBQUFBLE1BQ0Esd0JBQXdCLENBQUMsa0JBQWtCO0FBQ3ZDLGVBQU8sd0JBQXdCLElBQUksYUFBYTtBQUFBLE1BQ3BEO0FBQUEsTUFDQSx5QkFBeUIsQ0FBQyxlQUFlLGFBQWE7QUFDbEQsY0FBTSxvQkFBb0Isd0JBQXdCLElBQUksYUFBYTtBQUNuRSxZQUFJLENBQUMsbUJBQW1CO0FBQ3BCLGlCQUFPO0FBQUEsUUFDWDtBQUNBLGVBQU8sa0JBQWtCLGlCQUFpQixJQUFJLFFBQVE7QUFBQSxNQUMxRDtBQUFBLE1BQ0EsK0JBQStCLENBQUMsa0JBQWtCO0FBQzlDLGNBQU0sb0JBQW9CLHdCQUF3QixJQUFJLGFBQWE7QUFDbkUsWUFBSSxDQUFDLG1CQUFtQjtBQUNwQixpQkFBTyxDQUFBO0FBQUEsUUFDWDtBQUNBLGNBQU0sRUFBRSxtQkFBa0IsSUFBSztBQUMvQixlQUFPO0FBQUEsTUFDWDtBQUFBLE1BQ0EsdUNBQXVDLENBQUMsZUFBZSxVQUFVLE9BQU87QUFDcEUsY0FBTSxFQUFFLGdCQUFnQixDQUFBLEVBQUUsSUFBSztBQUMvQixjQUFNLHVCQUF1QkksTUFBQUEsMkJBQTJCLGVBQWU7QUFBQSxVQUNuRTtBQUFBLFFBQ2hCLENBQWE7QUFDRCxlQUFPLGtCQUFrQixzQkFBc0IsZUFBZSxhQUFhO0FBQUEsTUFDL0U7QUFBQSxNQUNBLCtDQUErQyxDQUFDLGVBQWUsWUFBWTtBQUN2RSxjQUFNLEVBQUUsZ0JBQWdCLENBQUEsRUFBRSxJQUFLO0FBQy9CLGNBQU0sc0JBQXNCQSxNQUFBQSwyQkFBMkIsZUFBZTtBQUFBLFVBQ2xFO0FBQUEsUUFDaEIsQ0FBYTtBQUdELGNBQU0sZ0NBQWdDLE9BQU8sd0JBQXdCLGFBQy9ELHNCQUNBLENBQUMsVUFBV0Msa0JBQUFBLElBQUsscUJBQXFCLEVBQUUsR0FBRyxNQUFLLENBQUU7QUFFeEQsZUFBTyxPQUFPLCtCQUErQixRQUFRLDJCQUEyQjtBQUVoRixlQUFPLGtCQUFrQiwrQkFBK0IsZUFBZSxhQUFhO0FBQUEsTUFDeEY7QUFBQSxJQUNSO0FBQUEsRUFDQTtBQ3hETyxRQUFNLDZCQUE2Qiw4QkFBNkI7QUFDdkUsUUFBTSxFQUFFLHVDQUF1Qyw4Q0FBNkMsSUFBTTtBQVk3RSx3Q0FBc0MsT0FBTztBQVUzRCxRQUFNLFNBQVMsc0NBQXNDLFVBQVU7QUFBQSxJQUNsRSxlQUFlLENBQUMsU0FBUztBQUFBLEVBQzdCLENBQUM7QUFRd0Isd0NBQXNDLFdBQVc7QUFDdEQsd0NBQXNDLE1BQU07QUFRakMsd0NBQXNDLGlCQUFpQjtBQVFuRCx3Q0FBc0MscUJBQXFCO0FBUXZGLFFBQU0sVUFBVSxzQ0FBc0MsU0FBUztBQVNoRCx3Q0FBc0MsUUFBUTtBQVE3RCxRQUFNLGFBQWEsc0NBQXNDLFlBQVk7QUFRbEQsd0NBQXNDLFlBQVk7QUFTckUsUUFBTSxPQUFPLHNDQUFzQyxNQUFNO0FBUXpDLHdDQUFzQyxTQUFTO0FBUWpELHdDQUFzQyxTQUFTO0FBQUEsSUFDaEUsZUFBZSxDQUFDLFNBQVM7QUFBQSxFQUM3QixDQUFDO0FBUU0sUUFBTSxRQUFRLHNDQUFzQyxPQUFPO0FBUTlDLHdDQUFzQyxRQUFRO0FBQUEsSUFDOUQsZUFBZSxDQUFDLFNBQVM7QUFBQSxFQUM3QixDQUFDO0FBUU0sUUFBTSxXQUFXLHNDQUFzQyxVQUFVO0FBSWhELHdDQUFzQyxVQUFVO0FBUTFDLHdDQUFzQyxnQkFBZ0I7QUFRekQsd0NBQXNDLGFBQWE7QUFRdkUsUUFBTSxTQUFTLHNDQUFzQyxRQUFRO0FBUWpELHdDQUFzQyxPQUFPO0FBQUEsSUFDNUQsZUFBZSxDQUFDLFNBQVM7QUFBQSxFQUM3QixDQUFDO0FBUU0sUUFBTSxPQUFPLHNDQUFzQyxNQUFNO0FBUTVDLHdDQUFzQyxNQUFNO0FBRTNDLHdDQUFzQyxPQUFPO0FBUXZDLHdDQUFzQyxhQUFhO0FBUWhELHdDQUFzQyxnQkFBZ0I7QUFRMUQsd0NBQXNDLFlBQVk7QUFRN0Msd0NBQXNDLGlCQUFpQjtBQVNqRSx3Q0FBc0MsT0FBTztBQVF2Qyx3Q0FBc0MsYUFBYTtBQVFyRCx3Q0FBc0MsV0FBVztBQVFsRCx3Q0FBc0MsVUFBVTtBQVEvQyx3Q0FBc0MsV0FBVztBQVEvQyx3Q0FBc0MsYUFBYTtBQVFyRCx3Q0FBc0MsV0FBVztBQVEvQyx3Q0FBc0MsYUFBYTtBQVN2RSxRQUFNLE1BQU0sc0NBQXNDLEtBQUs7QUFRakMsd0NBQXNDLGVBQWU7QUFRekQsd0NBQXNDLFdBQVc7QUFRL0Msd0NBQXNDLGFBQWE7QUFTdkUsUUFBTSxPQUFPLHNDQUFzQyxNQUFNO0FBUXZDLHdDQUFzQyxXQUFXO0FBUWxELHdDQUFzQyxVQUFVO0FBSTdDLHdDQUFzQyxhQUFhO0FBUTFELHdDQUFzQyxNQUFNO0FBUTFDLHdDQUFzQyxRQUFRO0FBUTVDLGdEQUE4QyxZQUFZO0FBQUEsSUFDOUUsNkJBQTZCO0FBQUE7QUFBQTtBQUFBO0FBQUE7QUFBQTtBQUFBO0FBQUE7QUFBQSxNQVF6QixZQUFZLHNDQUFzQyxzQkFBc0I7QUFBQSxRQUNwRSxlQUFlLENBQUMsU0FBUztBQUFBLE1BQ3JDLENBQVM7QUFBQSxJQUNUO0FBQUEsRUFDQSxDQUFDO0FBVW9CLHdDQUFzQyxPQUFPO0FBU3ZDLHdDQUFzQyxhQUFhO0FBU3JELHdDQUFzQyxXQUFXO0FBUzlDLHdDQUFzQyxjQUFjO0FBUXBELHdDQUFzQyxjQUFjO0FBVTNELHdDQUFzQyxPQUFPO0FBU3pDLHdDQUFzQyxXQUFXO0FBUy9DLHdDQUFzQyxhQUFhO0FBUTFELHdDQUFzQyxNQUFNO0FBU3ZDLHdDQUFzQyxXQUFXO0FBUTdDLHdDQUFzQyxpQkFBaUI7QUFBQSxJQUNoRixlQUFlLENBQUMsU0FBUztBQUFBLEVBQzdCLENBQUM7QUFVdUIsd0NBQXNDLFVBQVU7QUFVL0Msd0NBQXNDLFdBQVc7QUFTL0Msd0NBQXNDLGFBQWE7QUFlMUQsd0NBQXNDLE1BQU07QUFlN0Msd0NBQXNDLEtBQUs7QUFRbEMsd0NBQXNDLGNBQWM7QUFPekQsd0NBQXNDLFNBQVM7QUFRM0Msd0NBQXNDLGFBQWE7QUFRckQsd0NBQXNDLFdBQVc7QUFTN0Msd0NBQXNDLGVBQWU7QUFPeEQsd0NBQXNDLFFBQVE7QUFRaEQsd0NBQXNDLFVBQVU7QUFJekMsd0NBQXNDLGlCQUFpQjtBQUNuRCx3Q0FBc0MscUJBQXFCO0FBQzlELHdDQUFzQyxrQkFBa0I7QUFDL0Qsd0NBQXNDLFdBQVc7QUFDdkMsd0NBQXNDLHFCQUFxQjtBQUNwRCx3Q0FBc0MsNEJBQTRCO0FBQ2xFLHdDQUFzQyw0QkFBNEI7QUFDM0Usd0NBQXNDLG1CQUFtQjtBQUMzRCx3Q0FBc0MsaUJBQWlCO0FBQ3pELHdDQUFzQyxlQUFlO0FBQ25ELHdDQUFzQyxpQkFBaUI7QUFDekQsd0NBQXNDLGVBQWU7QUFDcEQsd0NBQXNDLGdCQUFnQjtBQVF2RCx3Q0FBc0MsZUFBZTtBQUt6Qyx3Q0FBc0MsNkJBQTZCO0FBQUEsSUFDeEcsZUFBZSxDQUFDLFNBQVM7QUFBQSxFQUM3QixDQUFDO0FBSzBDLHdDQUFzQywrQkFBK0I7QUFBQSxJQUM1RyxlQUFlLENBQUMsU0FBUztBQUFBLEVBQzdCLENBQUM7QUFJdUIsd0NBQXNDLFVBQVU7QUFPbEQsd0NBQXNDLFFBQVE7QUFJekMsd0NBQXNDLGVBQWU7QUFBQSxJQUM1RSxlQUFlLENBQUMsYUFBYSxVQUFVO0FBQUEsRUFDM0MsQ0FBQztBQUlxQix3Q0FBc0MsUUFBUTtBQUk5Qyx3Q0FBc0MsUUFBUTtBQUloRCx3Q0FBc0MsTUFBTTtBQUl4Qyx3Q0FBc0MsVUFBVTtBQUk1Qyx3Q0FBc0MsY0FBYztBQVVsRCx3Q0FBc0MsZ0JBQWdCO0FBVTdELHdDQUFzQyxTQUFTO0FBSTdDLHdDQUFzQyxXQUFXO0FDbHNCMUUsUUFBTSxlQUFlQyxPQUFBQSxjQUFjLElBQUk7QUF5Q0gsZUFBYTtBQzFCakQsUUFBTSxtQkFBbUI7QUFFekIsVUFBUSxPQUFPLENBQUMsRUFBRSxjQUFjO0FBQzlCLFdBQU8sZ0JBQUFQLE9BQUEsY0FBQyxnQkFBYSxRQUFBLENBQWtCO0FBQUEsRUFDekMsQ0FBQztBQUVELFFBQU0sZUFBZSxDQUFDLEVBQUUsY0FBYzs7QUFDcEMsVUFBTSxDQUFDLFNBQVMsVUFBVSxJQUFJUSxPQUFBQSxTQUFTLElBQUk7QUFDM0MsVUFBTSxDQUFDLGFBQWEsY0FBYyxJQUFJQSxPQUFBQSxTQUFTLEVBQUU7QUFDakQsVUFBTSxDQUFDLGNBQWMsZUFBZSxJQUFJQSxPQUFBQSxTQUFTLEVBQUU7QUFDbkQsVUFBTSxDQUFDLGlCQUFpQixrQkFBa0IsSUFBSUEsT0FBQUEsU0FBUyxFQUFFO0FBQ3pELFVBQU0sQ0FBQyxnQkFBZ0IsaUJBQWlCLElBQUlBLE9BQUFBLFNBQVMsTUFBTTtBQUMzRCxVQUFNLENBQUMsbUJBQW1CLG9CQUFvQixJQUFJQSxPQUFBQSxTQUFTLEVBQUU7QUFFN0QsVUFBTSxlQUFlLFlBQVk7O0FBQy9CLGlCQUFXLElBQUk7QUFDZixzQkFBZ0IsRUFBRTtBQUNsQixxQkFBZSxFQUFFO0FBRWpCLFVBQUk7QUFDRixjQUFNLFdBQVcsTUFBTSxRQUFRO0FBQUEsVUFDbkMsR0FBRyxnQkFBZ0I7QUFBQSxVQUNuQjtBQUFBLFlBQ0UsUUFBUTtBQUFBLFlBQ1IsU0FBUztBQUFBLFVBQUE7QUFBQSxRQUNYO0FBR0ksWUFBSSxDQUFDLFNBQVMsSUFBSTtBQUNoQixnQkFBTSxJQUFJLE1BQU0sMkJBQTJCLFNBQVMsTUFBTSxFQUFFO0FBQUEsUUFDOUQ7QUFFQSxjQUFNLE9BQU8sTUFBTSxTQUFTLEtBQUE7QUFDNUIsNkJBQW1CQyxNQUFBLDZCQUFNLGFBQU4sZ0JBQUFBLElBQWdCLG9CQUFtQixFQUFFO0FBQ3hELDRCQUFrQkMsTUFBQSw2QkFBTSxhQUFOLGdCQUFBQSxJQUFnQixtQkFBa0IsTUFBTTtBQUMxRCwrQkFBcUIsa0NBQU0sYUFBTixtQkFBZ0Isc0JBQXFCLEVBQUU7QUFBQSxNQUM5RCxTQUFTLEtBQUs7QUFDWixnQkFBUSxNQUFNLDJCQUEyQixHQUFHO0FBQzVDLHdCQUFnQixlQUFlLFFBQVEsSUFBSSxVQUFVLGVBQWU7QUFBQSxNQUN0RSxVQUFBO0FBQ0UsbUJBQVcsS0FBSztBQUFBLE1BQ2xCO0FBQUEsSUFDRjtBQUVBLFVBQU0sZUFBZSxZQUFZO0FBQy9CLHNCQUFnQixFQUFFO0FBQ2xCLHFCQUFlLEVBQUU7QUFFakIsVUFBSTtBQUNGLGNBQU0sV0FBVyxNQUFNLFFBQVE7QUFBQSxVQUNuQyxHQUFHLGdCQUFnQjtBQUFBLFVBQ25CO0FBQUEsWUFDRSxRQUFRO0FBQUEsWUFDUixTQUFTO0FBQUEsWUFDVCxNQUFNO0FBQUEsY0FDSjtBQUFBLGNBQ0E7QUFBQSxjQUNBO0FBQUEsWUFBQTtBQUFBLFVBQ0Y7QUFBQSxRQUNGO0FBR0ksWUFBSSxDQUFDLFNBQVMsSUFBSTtBQUNoQixnQkFBTSxJQUFJLE1BQU0sMkJBQTJCLFNBQVMsTUFBTSxFQUFFO0FBQUEsUUFDOUQ7QUFFQSxjQUFNLE9BQU8sTUFBTSxTQUFTLEtBQUE7QUFDNUIsdUJBQWUsWUFBWSxLQUFLLFVBQVUsRUFBRTtBQUFBLE1BQzlDLFNBQVMsS0FBSztBQUNaLGdCQUFRLE1BQU0sMkJBQTJCLEdBQUc7QUFDNUMsd0JBQWdCLGVBQWUsUUFBUSxJQUFJLFVBQVUsZUFBZTtBQUFBLE1BQ3RFO0FBQUEsSUFDRjtBQUVBQyxJQUFBQSxPQUFBQSxVQUFVLE1BQU07QUFDZCxtQkFBQSxFQUFlO0FBQUEsUUFBTSxDQUFDLFFBQ3BCLFFBQVEsTUFBTSxrQ0FBa0MsR0FBRztBQUFBLE1BQUE7QUFBQSxJQUV2RCxHQUFHLENBQUEsQ0FBRTtBQUVMLFdBQ0UsZ0JBQUFYLE9BQUEsY0FBQyxNQUFBLEVBQUssV0FBVSxVQUFTLEtBQUksWUFDM0IsZ0JBQUFBLE9BQUEsY0FBQyxZQUFBLEVBQVcsT0FBTSx1QkFBc0IsUUFBTyxtREFDNUMsTUFBQSxNQUFLLCtGQUVOLENBQ0YsR0FFQSxnQkFBQUEsT0FBQSxjQUFDLFNBQUEsSUFBUSxHQUVULGdCQUFBQSxPQUFBLGNBQUMsS0FBQSxNQUNDLGdCQUFBQSxPQUFBLGNBQUMsTUFBQSxFQUFLLFFBQVEsRUFBRSxZQUFZLFNBQU8sR0FBRyxnQkFBYyxHQUNwRCxnQkFBQUEsT0FBQSxjQUFDLE1BQUEsTUFBTSxVQUFVLHdCQUF3QixPQUFRLEdBQ2pELGdCQUFBQSxPQUFBLGNBQUMsTUFBQSxNQUFNLGVBQWUsVUFBVSxZQUFZLEtBQUssbUNBQW9DLEdBQ3JGLGdCQUFBQSxPQUFBLGNBQUMsTUFBQSxNQUFNLGNBQWMsY0FBYyw2QkFBOEIsQ0FDbkUsR0FFQSxnQkFBQUEsT0FBQSxjQUFDLFNBQUEsSUFBUSxHQUVULGdCQUFBQSxPQUFBO0FBQUEsTUFBQztBQUFBLE1BQUE7QUFBQSxRQUNDLGdCQUFnQjtBQUFBLFFBQ2hCLFVBQVUsTUFBTTtBQUNkLHVCQUFBLEVBQWU7QUFBQSxZQUFNLENBQUMsUUFDcEIsUUFBUSxNQUFNLGtDQUFrQyxHQUFHO0FBQUEsVUFBQTtBQUFBLFFBRXZEO0FBQUEsTUFBQTtBQUFBLE1BRUEsZ0JBQUFBLE9BQUEsY0FBQyxNQUFBLEVBQUssV0FBVSxVQUFTLEtBQUksWUFDM0IsZ0JBQUFBLE9BQUE7QUFBQSxRQUFDO0FBQUEsUUFBQTtBQUFBLFVBQ0MsT0FBTTtBQUFBLFVBQ04sTUFBSztBQUFBLFVBQ0wsT0FBTztBQUFBLFVBQ1AsVUFBVSxDQUFDLFVBQVUsbUJBQW1CLEtBQUs7QUFBQSxVQUM3QyxhQUFZO0FBQUEsUUFBQTtBQUFBLE1BQUEsR0FHZCxnQkFBQUEsT0FBQTtBQUFBLFFBQUM7QUFBQSxRQUFBO0FBQUEsVUFDQyxPQUFNO0FBQUEsVUFDTixNQUFLO0FBQUEsVUFDTCxPQUFPO0FBQUEsVUFDUCxVQUFVLENBQUMsVUFBVSxrQkFBa0IsT0FBTyxLQUFLLENBQUM7QUFBQSxVQUNwRCxTQUFTO0FBQUEsWUFDUCxFQUFFLE9BQU8sWUFBWSxPQUFPLFdBQUE7QUFBQSxZQUM1QixFQUFFLE9BQU8sUUFBUSxPQUFPLE9BQUE7QUFBQSxZQUN4QixFQUFFLE9BQU8sVUFBVSxPQUFPLFNBQUE7QUFBQSxVQUFTO0FBQUEsUUFDckM7QUFBQSxNQUFBLEdBR0YsZ0JBQUFBLE9BQUE7QUFBQSxRQUFDO0FBQUEsUUFBQTtBQUFBLFVBQ0MsT0FBTTtBQUFBLFVBQ04sTUFBSztBQUFBLFVBQ0wsT0FBTztBQUFBLFVBQ1AsVUFBVSxDQUFDLFVBQVUscUJBQXFCLEtBQUs7QUFBQSxVQUMvQyxhQUFhO0FBQUEsVUFDYixhQUFZO0FBQUEsUUFBQTtBQUFBLE1BQUEsR0FHZCxnQkFBQUEsT0FBQSxjQUFDLFFBQUEsRUFBTyxNQUFLLFNBQUEsR0FBUyxlQUFhLENBQ3JDO0FBQUEsSUFBQSxHQUdGLGdCQUFBQSxPQUFBLGNBQUMsU0FBQSxJQUFRLHdDQUVSLEtBQUEsTUFDQyxnQkFBQUEsT0FBQSxjQUFDLE1BQUEsRUFBSyxRQUFRLEVBQUUsWUFBWSxTQUFPLEdBQUcsZUFBYSxHQUNuRCxnQkFBQUEsT0FBQSxjQUFDLE1BQUEsTUFBSyxlQUFZLFNBQU8sd0NBQVMsV0FBVCxtQkFBaUIsT0FBTSxTQUFTLENBQUUsR0FDM0QsZ0JBQUFBLE9BQUEsY0FBQyxNQUFBLE1BQUssYUFBVSxTQUFPLHdDQUFTLFNBQVQsbUJBQWUsT0FBTSxTQUFTLENBQUUsQ0FDekQsQ0FDRjtBQUFBLEVBRUo7OyIsInhfZ29vZ2xlX2lnbm9yZUxpc3QiOlswLDEsMiwzLDQsNSw2LDddfQ==
