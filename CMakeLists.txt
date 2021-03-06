cmake_minimum_required(VERSION 3.13)

project(CLGEN, 
        VERSION 0.0.1
        DESCRIPTION "Programming language model using machine learning")
# TODO check
# https://cmake.org/cmake/help/v3.0/module/FindPythonInterp.html
cmake_policy(SET CMP0076 NEW)

###### Important app paths
# Python application relative base path
set(APP_PATH    deeplearning/clgen)
# Base path of third_party deps
set(THIRD_PARTY ${CMAKE_BINARY_DIR}/third_party)
# Local bin folder for application binaries and libraries
set(LOCAL       ${CMAKE_BINARY_DIR}/local)

OPTION(BOOST_FROM_SOURCE 
       "Select to build boost locally from source." 
       OFF
)

function(find_binaries)

    ## For python and protoc executables:
    # 1. Find if the provided or default binaries exist.
    # 2. If they don't set flags to install from source locally.

    # Append to python default if PYTHON variable is not explicitly defined.
    if ("${PYTHON}" STREQUAL "")
      set(PYTHON python3 CACHE FILEPATH
        "Provide specific python for application. Default: [python3]. Ignored if BUILD_FROM_SOURCE is enabled."
        FORCE
      )
    endif()

    # Append to protoc default if PROTOC variable is not explicitly defined.
    if ("${PROTOC}" STREQUAL "")
      set(PROTOC protoc CACHE FILEPATH
        "Provide specific protobuf compiler for application. Default: [protoc]. Ignored if BUILD_FROM_SOURCE is enabled."
        FORCE
      )
    endif()

    # For legacy reasons, both LLVM 6 and 10 are needed.
    set(LLVM_VERSION "10" CACHE FILEPATH
      "Select between LLVM version 6 and 10. Both are build from source. [Default: 10]."
      FORCE
    )
    set(LLVM_VERSION6 "6" CACHE FILEPATH
      "Select between LLVM version 6 and 10. Both are build from source. [Default: 10]."
      FORCE
    )
    message("-- Using LLVM " ${LLVM_VERSION} " and " ${LLVM_VERSION6})

    # Python binary exists or crash.
    find_program(PYTHON_FOUND ${PYTHON})
    if (PYTHON_FOUND)
      message("-- Python binary found in " ${PYTHON_FOUND})
      set(PYTHON_FROM_SOURCE OFF PARENT_SCOPE)
    elseif (NOT PYTHON_FOUND)
      message(WARNING "-- Python binary " ${PYTHON_FOUND} " not found. Will install python3.7 from source.")
      set(PYTHON_FROM_SOURCE ON PARENT_SCOPE)
    else()
        message(FATAL_ERROR "-- Unknown python binary error. Aborting.")
    endif()

    # protoc binary exists or crash.
    find_program(PROTOC_FOUND ${PROTOC})
    if (PROTOC_FOUND)
      message("-- protoc binary found in " ${PROTOC_FOUND})
      set(PROTOC_FROM_SOURCE OFF PARENT_SCOPE)
    elseif (NOT PROTOC_FOUND)
      message(WARNING "-- protoc binary " ${PROTOC_FOUND} " not found. Will install from source.")
      set(PROTOC_FROM_SOURCE ON PARENT_SCOPE)
    else()
        message(FATAL_ERROR "-- Unknown protoc binary error. Aborting.")
    endif()
endfunction()

function(install_external_deps)

  ## If triggered, install python, protoc, boost from source and set paths.
  # Also, install opencl-headers and llvm-6 locally.

  include(ExternalProject)
  if (PYTHON_FROM_SOURCE)
    # Python 3.7.5 from source
    ExternalProject_Add(python
      URL               https://www.python.org/ftp/python/3.7.5/Python-3.7.5.tar.xz
      URL_MD5           08ed8030b1183107c48f2092e79a87e2
      PREFIX            ${THIRD_PARTY}
      TMP_DIR           ${THIRD_PARTY}/tmp
      STAMP_DIR         ${THIRD_PARTY}/stamp
      DOWNLOAD_DIR      ${THIRD_PARTY}/python
      SOURCE_DIR        ${THIRD_PARTY}/python/python
      BUILD_IN_SOURCE   true
      INSTALL_DIR       ${LOCAL}
      CONFIGURE_COMMAND ${THIRD_PARTY}/python/python/configure --prefix=${LOCAL} --enable-optimizations --enable-loadable-sqlite-extensions
    )
    set(PYTHON          ${LOCAL}/bin/python3.7 PARENT_SCOPE)
  endif()

  if (BOOST_FROM_SOURCE)
    # Boost lib
    # TODO make sure this version is visible when compiling kernels
    ExternalProject_Add(boost
      URL               https://dl.bintray.com/boostorg/release/1.73.0/source/boost_1_73_0.tar.gz
      URL_HASH          SHA256=9995e192e68528793755692917f9eb6422f3052a53c5e13ba278a228af6c7acf
      PREFIX            ${THIRD_PARTY}
      TMP_DIR           ${THIRD_PARTY}/tmp
      STAMP_DIR         ${THIRD_PARTY}/stamp
      DOWNLOAD_DIR      ${THIRD_PARTY}/boost
      SOURCE_DIR        ${THIRD_PARTY}/boost/boost
      BUILD_IN_SOURCE   true
      INSTALL_DIR       ${LOCAL}
      CONFIGURE_COMMAND ${THIRD_PARTY}/boost/boost/bootstrap.sh --prefix=${LOCAL}
      BUILD_COMMAND     ${THIRD_PARTY}/boost/boost/b2  --prefix=${LOCAL} && ${THIRD_PARTY}/boost/boost/b2 --prefix=${LOCAL} headers
      INSTALL_COMMAND   ${THIRD_PARTY}/boost/boost/b2 install
    )
    set(BOOST           ${LOCAL} PARENT_SCOPE)
  endif()

  if (PROTOC_FROM_SOURCE)
    # protoc compiler
    ExternalProject_Add(protobuf
      GIT_REPOSITORY    https://github.com/protocolbuffers/protobuf.git
      GIT_TAG           31ebe2ac71400344a5db91ffc13c4ddfb7589f92
      GIT_PROGRESS      true
      BUILD_IN_SOURCE   true
      PREFIX            ${THIRD_PARTY}
      TMP_DIR           ${THIRD_PARTY}/tmp
      STAMP_DIR         ${THIRD_PARTY}/stamp
      SOURCE_DIR        ${THIRD_PARTY}/protobuf/protobuf
      INSTALL_DIR       ${LOCAL}
      CONFIGURE_COMMAND cd ${THIRD_PARTY}/protobuf/protobuf && ./autogen.sh && ${THIRD_PARTY}/protobuf/protobuf/configure --prefix=${LOCAL}
    )
    set(PROTOC          ${LOCAL}/bin/protoc PARENT_SCOPE)
  endif ()

  ## onnx model
  #ExternalProject_Add(onnx
  #  GIT_REPOSITORY    https://github.com/onnx/onnx.git
  #  GIT_TAG           685898bc6f3fd6eb16ba129ea990f96330537e38
  #  GIT_PROGRESS      true
  #  BUILD_IN_SOURCE   true
  #  PREFIX            ${THIRD_PARTY}
  #  TMP_DIR           ${THIRD_PARTY}/tmp
  #  STAMP_DIR         ${THIRD_PARTY}/stamp
  #  SOURCE_DIR        ${THIRD_PARTY}/onnx/onnx
  #  INSTALL_DIR       ${LOCAL}
  #)
  #set(ONNX          ${LOCAL}/onnx PARENT_SCOPE)

  ExternalProject_Add(llvm6
    URL               https://releases.llvm.org/6.0.0/clang+llvm-6.0.0-x86_64-linux-gnu-ubuntu-16.04.tar.xz
    PREFIX            ${THIRD_PARTY}
    TMP_DIR           ${THIRD_PARTY}/tmp
    STAMP_DIR         ${THIRD_PARTY}/stamp
    DOWNLOAD_DIR      ${THIRD_PARTY}/llvm6
    SOURCE_DIR        ${THIRD_PARTY}/llvm6/llvm6
    INSTALL_DIR       ${LOCAL}
    CONFIGURE_COMMAND ""
    BUILD_COMMAND     ""
    INSTALL_COMMAND   cp -Rn ${THIRD_PARTY}/llvm6/llvm6/ ${LOCAL}
  )
  ExternalProject_Add(llvm
    GIT_REPOSITORY    https://github.com/llvm/llvm-project.git
    GIT_TAG           ef32c611aa214dea855364efd7ba451ec5ec3f74
    GIT_PROGRESS      true
    PREFIX            ${THIRD_PARTY}
    TMP_DIR           ${THIRD_PARTY}/tmp
    STAMP_DIR         ${THIRD_PARTY}/stamp
    DOWNLOAD_DIR      ${THIRD_PARTY}/llvm
    SOURCE_DIR        ${THIRD_PARTY}/llvm/llvm
    INSTALL_DIR       ${LOCAL}
    LIST_SEPARATOR    |
    CONFIGURE_COMMAND cd ${THIRD_PARTY}/llvm/llvm && ${CMAKE_COMMAND} -S llvm -B build -DLLVM_ENABLE_PROJECTS=clang|libcxx|libcxxabi -DCMAKE_INSTALL_PREFIX=${LOCAL}/llvm -DLLVM_ENABLE_ASSERTIONS=ON -DCMAKE_BUILD_TYPE=Release
    BUILD_COMMAND     cd ${THIRD_PARTY}/llvm/llvm/build && $(MAKE)
    INSTALL_COMMAND   cd ${THIRD_PARTY}/llvm/llvm/build && $(MAKE) install
  )
  set(LLVM6           ${LOCAL}/llvm6 PARENT_SCOPE)
  set(LLVM            ${LOCAL}/llvm  PARENT_SCOPE)
  # #include <CL/*>
  # I have forked my own version of OpenCL Headers which I install here.
  # My version excludes the C-API functions from being included,
  # otherwise many compilation errors will come up when trying to
  # compile pure cl files instead of driving them through a C-file.
  ExternalProject_Add(opencl-headers
    GIT_REPOSITORY    https://github.com/fivosts/OpenCL-Headers.git
    GIT_TAG           ee7c1831c40e2d8ba9ce62fffe9cade64bcf40e7
    GIT_PROGRESS      true
    PREFIX            ${THIRD_PARTY}
    TMP_DIR           ${THIRD_PARTY}/tmp
    STAMP_DIR         ${THIRD_PARTY}/stamp
    SOURCE_DIR        ${THIRD_PARTY}/opencl_headers/opencl_headers
    INSTALL_DIR       ${LOCAL}
    CONFIGURE_COMMAND ""
    BUILD_COMMAND     ""
    INSTALL_COMMAND   cp -Rn ${THIRD_PARTY}/opencl_headers/opencl_headers/ ${LOCAL}
  )
  set(OPENCL_HEADERS  ${LOCAL}/opencl_headers PARENT_SCOPE)

  # TODO check if needed.
  # ExternalProject_Add(opencl-icd-loader
  #   GIT_REPOSITORY    https://https://github.com/KhronosGroup/OpenCL-ICD-Loader
  #   GIT_TAG           c7fda8bb042760b5ead8650c64445f5972a64ad7
  #   GIT_PROGRESS      true
  #   DEPENDS           ${includes}
  #   PREFIX            ${THIRD_PARTY}
  #   TMP_DIR           ${THIRD_PARTY}/tmp
  #   STAMP_DIR         ${THIRD_PARTY}/stamp
  #   SOURCE_DIR        ${THIRD_PARTY}/opencl_icd_loader/opencl_icd_loader
  #   BINARY_DIR        ${THIRD_PARTY}/opencl_icd_loader/build
  #   INSTALL_DIR       ${LOCAL}
  #   # CONFIGURE_COMMAND 
  #   # BUILD_COMMAND     ${THIRD_PARTY}/boost/boost/b2 && ${THIRD_PARTY}/boost/boost/b2 headers
  #   # INSTALL_COMMAND   ${THIRD_PARTY}/boost/boost/b2 install
  # )
endfunction()

function(setup_python)

  ### Initialize python environment for application
  # 1. Create virtual environment for python (depends on 'venv')
  # 2. Pip install requirements.pip
  # 3. Set python binary to virtual environment's bin folder

  set (PYTHON_ENV ${LOCAL}/env/bin/python)
  if (PYTHON_FROM_SOURCE)
    file(MAKE_DIRECTORY ${LOCAL}/lib/python)
    add_custom_target(requirements ALL
      COMMAND ${PYTHON} -m venv ${LOCAL}/env
      COMMAND ${PYTHON_ENV} -m pip install wheel setuptools==53.1.0
      COMMAND ${PYTHON_ENV} -m pip install --upgrade pip==21.0.1
      COMMAND ${PYTHON_ENV} -m pip install --disable-pip-version-check --upgrade -r ${CMAKE_SOURCE_DIR}/requirements.pip
      DEPENDS python
      COMMENT "Installing python package dependencies"
    )
  else ()
    add_custom_target(requirements ALL
      COMMAND ${PYTHON} -m venv ${LOCAL}/env
      COMMAND ${PYTHON_ENV} -m pip install wheel setuptools==53.1.0
      COMMAND ${PYTHON_ENV} -m pip install --upgrade pip==21.0.1
      COMMAND ${PYTHON_ENV} -m pip install --disable-pip-version-check --upgrade -r ${CMAKE_SOURCE_DIR}/requirements.pip
      COMMENT "Installing python package dependencies"
    )
  endif ()
  if ("${LLVM_VERSION}" STREQUAL "10")
    # Override pip clang 12 and install 9
    add_custom_target(override_pyclang ALL
      COMMAND ${PYTHON} -m pip uninstall --yes clang
      COMMAND ${PYTHON} -m pip install clang==10.0.1
      DEPENDS requirements
      COMMENT "Overriding pip clang installation to 10.0."
    )
  endif()
  set(PYTHON ${PYTHON_ENV} PARENT_SCOPE)
endfunction()

function(clgen)

  ### Auto-generates clgen binary that initializes app environment and deploys app.

  get_target_property(CLANG_REWRITER      clang_rewriter      path)
  get_target_property(DASHBOARD_STATIC    dashboard_static    path)
  get_target_property(DASHBOARD_TEMPLATES dashboard_templates path)
  get_target_property(LIBCLC              libclc              path)
  get_target_property(DATA_CL_INCLUDE     data_cl_include     path)
  get_target_property(GREWE               Grewe               path)
  get_target_property(INSTCOUNT           InstCount           path)
  get_target_property(AUTOPHASE           Autophase           path)

  string(CONCAT CLGEN 
    "##############################\n"
    "# Auto generated bash binary #\n"
    "# ---------  CLGEN ----------#\n"
    "#       Not to be edited     #\n"
    "##############################\n"
    "PYTHON_BINARY="                         ${PYTHON}  "\n"
    "CLGEN_BINARY="                          ${CMAKE_CURRENT_SOURCE_DIR}/${APP_PATH} "/clgen.py\n"
    "export LLVM="                           ${LLVM} "\n"
    "export LLVM_VERSION="                   ${LLVM_VERSION} "\n"
    "export LLVM_LIB="                       ${LLVM}/lib "\n"
    "export LIBCXX_HEADERS="                 ${LLVM}/include/c++/v1 "\n"
    "export LIBCLC="                         ${LIBCLC} "\n"
    "export OPENCL_HEADERS="                 ${OPENCL_HEADERS} "\n"
    "export CLANG="                          ${LLVM}/bin/clang "\n"
    "export OPT="                            ${LLVM}/bin/opt "\n"
    "export DASHBOARD_TEMPLATES="            ${DASHBOARD_TEMPLATES} "\n"
    "export DASHBOARD_STATIC="               ${DASHBOARD_STATIC} "\n"
    "export DATA_CL_INCLUDE="                ${DATA_CL_INCLUDE} "\n"
    "export AUX_INCLUDE="                    ${DATA_CL_INCLUDE} "/aux_include" "\n"
    "export CLANG_FORMAT="                   ${LLVM}/bin/clang-format "\n"
    "export CLANG_HEADERS="                  ${LLVM}/lib/clang/${LLVM_VERSION}.0.1/include "\n"
    "export CLANG_REWRITER="                 ${CLANG_REWRITER} "\n"
    "export GREWE="                          ${GREWE} "\n"
    "export INSTCOUNT="                      ${INSTCOUNT} "\n"
    "export AUTOPHASE="                      ${AUTOPHASE} "\n"
    "eval PYTHONPATH="                       ${CMAKE_CURRENT_SOURCE_DIR} " $PYTHON_BINARY $CLGEN_BINARY \"$@\"\n"
    "unset LLVM\n"
    "unset LLVM_VERSION\n"
    "unset LLVM_LIB\n"
    "unset LIBCXX_HEADERS\n"
    "unset LIBCLC\n"
    "unset OPENCL_HEADERS\n"
    "unset CLANG\n"
    "unset OPT\n"
    "unset DASHBOARD_TEMPLATES\n"
    "unset DASHBOARD_STATIC\n"
    "unset DATA_CL_INCLUDE\n"
    "unset AUX_INCLUDE\n"
    "unset CLANG_FORMAT\n"
    "unset CLANG_HEADERS\n"
    "unset GREWE\n"
    "unset INSTCOUNT\n"
    "unset AUTOPHASE\n"
  )
  file(
    WRITE ${CMAKE_BINARY_DIR}/${APP_PATH}/clgen ${CLGEN}
  )
  add_custom_target(clgen ALL
    COMMAND ${CMAKE_COMMAND} -E create_symlink ${CMAKE_BINARY_DIR}/${APP_PATH}/clgen ${CMAKE_CURRENT_SOURCE_DIR}/clgen
    COMMAND chmod 551 ${CMAKE_CURRENT_SOURCE_DIR}/clgen
  )
endfunction()

find_binaries()
install_external_deps()
setup_python()
add_subdirectory(${APP_PATH}/dashboard)
add_subdirectory(${APP_PATH}/data)
add_subdirectory(${APP_PATH}/features)
add_subdirectory(${APP_PATH}/preprocessors)
add_subdirectory(${APP_PATH}/proto)
clgen()
