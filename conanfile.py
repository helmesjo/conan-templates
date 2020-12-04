#!/usr/bin/env python
# -*- coding: utf-8 -*-

from conans import ConanFile, CMake, tools, AutoToolsBuildEnvironment
import os
import re

def replace(file, pattern, subst):
    # Read contents from file as a single string
    file_handle = open(file, 'r')
    file_string = file_handle.read()
    file_handle.close()

    # Use RE package to allow for replacement (also allowing for (multiline) REGEX)
    file_string = (re.sub(pattern, "{} # <-- Line edited by conan package -->".format(subst), file_string))

    # Write contents to file.
    # Using mode 'w' truncates the file.
    file_handle = open(file, 'w')
    file_handle.write(file_string)
    file_handle.close()

# Building Thrift for C++: https://github.com/apache/thrift/blob/cecee50308fc7e6f77f55b3fd906c1c6c471fa2f/lib/cpp/README.md
class ThriftConan(ConanFile):
    name = "thrift"
    version = "0.13.0"
    description =   "Thrift is a lightweight, \
                    language-independent software \
                    stack with an associated code \
                    generation mechanism for RPC."
    url = "https://github.com/helmesjo/conan-thrift"
    homepage = "https://thrift.apache.org/"
    author = "helmesjo <helmesjo@gmail.com>"
    license = "Apache License 2.0"
    exports = ["LICENSE.md"]

    exports_sources = ["CMakeLists.txt"]
    generators = "cmake"

    source_subfolder = "source_subfolder"
    build_subfolder = "build_subfolder"

    # http://thrift.apache.org/docs/install/
    requires = (
        "boost/1.74.0",
    )

    settings = "os", "arch", "compiler", "build_type"
    options = {
        "shared": [True, False],
        "fPIC": [True, False],
        "with_zlib": [True, False],
        "with_libevent": [True, False],
        "with_qt4": [True, False],
        "with_qt5": [True, False],
        "with_openssl": [True, False],
        "with_c_glib": [True, False],
        "with_cpp": [True, False],
        "with_java": [True, False],
        "with_python": [True, False],
        "with_haskell": [True, False],
        "with_plugin": [True, False],
        "build_libraries": [True, False],
        "build_compiler": [True, False],
        "build_testing": [True, False],
        "build_examples": [True, False],
        "build_tutorials": [True, False],
    }

    default_options = (
        "shared=False",
        "fPIC=True",
        "with_zlib=True",
        "with_libevent=True",
        "with_qt4=False",
        "with_qt5=False",
        "with_openssl=True",
        "with_c_glib=False",
        "with_cpp=True",
        "with_java=False",
        "with_python=False",
        "with_haskell=False",
        "with_plugin=False",
        "build_libraries=True",
        "build_compiler=True",
        "build_testing=False", # Currently fails if 'True' because of too recent boost::test version (?) in package
        "build_examples=False",
        "build_tutorials=False",
        "boost:header_only=True",
    )

    def config_options(self):
        if self.settings.os == 'Windows':
            del self.options.fPIC

    def configure(self):
        if self.settings.compiler != 'Visual Studio' and self.options.shared:
            self.options['boost'].add_option('fPIC', 'True')

        # Thrift supports shared libs but it requires some work with this recipe, so skipping for now.
        if self.settings.os == "Windows" and self.options.shared:
            self.output.warn("Thrift supports shared libs but it requires some work with this recipe, so forcing static...")
            self.options.shared = False

    def requirements(self):
        if self.settings.os == 'Windows':
            self.requires("winflexbison/2.5.20@bincrafters/stable")
        else:
            self.requires("flex_installer/2.6.4@bincrafters/stable")
            self.requires("bison_installer/3.3.2@bincrafters/stable")
            
        if self.options.with_openssl:
            self.requires("openssl/1.1.1d")
        if self.options.with_zlib:
            self.requires("zlib/1.2.11")
        if self.options.with_libevent:
            self.requires("libevent/2.1.12")

    def source(self):
        source_url = "https://github.com/apache/thrift"
        tools.get("{0}/archive/{1}.tar.gz".format(source_url, self.version))
        extracted_dir = self.name + "-" + self.version

        #Rename to "source_subfolder" is a convention to simplify later steps
        os.rename(extracted_dir, self.source_subfolder)

        define_options_cmakelist_path = os.path.join(self.source_subfolder ,"build/cmake/DefineOptions.cmake")
        # Stop thrift from incorrectly overriding 'BUILD_SHARED_LIBS' (to allow building static on Linux & macOS)
        replace(define_options_cmakelist_path, r"(.*CMAKE_DEPENDENT_OPTION\(BUILD_SHARED_LIBS)", r"# \1")

    def configure_cmake(self):
        def add_cmake_option(option, value):
            var_name = "{}".format(option).upper()
            value_str = "{}".format(value)
            var_value = "ON" if value_str == 'True' else "OFF" if value_str == 'False' else value_str 
            cmake.definitions[var_name] = var_value

        cmake = CMake(self)

        if self.settings.os != 'Windows':
            cmake.definitions['CMAKE_POSITION_INDEPENDENT_CODE'] = self.options.fPIC

        for option, value in self.options.items():
            add_cmake_option(option, value)

        cmake.definitions["BOOST_ROOT"] = self.deps_cpp_info['boost'].rootpath

        # Make optional libs "findable"
        if self.options.with_openssl:
            cmake.definitions["OPENSSL_ROOT_DIR"] = self.deps_cpp_info['openssl'].rootpath
        if self.options.with_zlib:
            cmake.definitions["ZLIB_ROOT"] = self.deps_cpp_info['zlib'].rootpath
        if self.options.with_libevent:
            cmake.definitions["LIBEVENT_ROOT"] = self.deps_cpp_info['libevent'].rootpath

        cmake.configure(build_folder=self.build_subfolder)
        return cmake

    def build(self):
        cmake = self.configure_cmake()
        cmake.build()

        if self.options.build_testing:
            self.output.info("Running {} tests".format(self.name))
            source_path = os.path.join(self.build_subfolder, self.source_subfolder)
            with tools.chdir(source_path):
                self.run("ctest . --build-config {}".format(self.settings.build_type))
        
    def package(self):
        self.copy(pattern="LICENSE", dst="licenses", src=self.source_subfolder)
        cmake = self.configure_cmake()
        cmake.install()
        build_source_dir = os.path.join(self.build_subfolder, self.source_subfolder)
        # Copy generated headers from build tree
        self.copy(pattern="*.h", dst="include", src=build_source_dir, keep_path=True)

    def package_info(self):
        # Make 'thrift' compiler available to consumers
        self.env_info.path.append(os.path.join(self.package_folder, "bin"))
        self.cpp_info.libs = tools.collect_libs(self)
        # Make sure libs are link in correct order. Important thing is that libthrift/thrift is last
        # (a little naive to sort, but libthrift/thrift should end up last since rest of the libs extend it with an abbrevation: 'thriftnb', 'thriftz')
        # The library that needs symbols must be first, then the library that resolves the symbols should come after.
        self.cpp_info.libs.sort(reverse = True)

        if self.settings.os == "Windows":
            self.cpp_info.defines.append("NOMINMAX") # To avoid error C2589: '(' : illegal token on right side of '::'